import json
import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from pet.agent.brain import _explicit_write_intent, run_pet
from pet.agent.database import execute_database_tool
from pet.agent.nvidia import NemotronError, ask_nemotron
from pet.evolution import add_xp
from pet.models import PetChatSession, PetConversation, PetMemory, PetProfile
from workspace.models import Activity, Idea, Project, Skill, Task, UserSettings


class PetApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pet-owner", password="test-password-123")
        self.other = User.objects.create_user(username="other-owner", password="test-password-123")
        self.pet = PetProfile.objects.create(owner=self.user, name="Voxie")
        self.client.force_login(self.user)

    def test_pet_page_renders_companion_interface(self):
        response = self.client.get(reverse("pet"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pet-chat-form")
        self.assertContains(response, "MEMORY VAULT")
        self.assertContains(response, "Voxie")

    def test_conversation_object_tokens_become_workspace_links(self):
        project = Project.objects.create(owner=self.user, title="TOEFL 2026", description="Study plan")
        token = f"[project:{project.pk}]"
        PetConversation.objects.create(
            pet=self.pet,
            user_message="Open my project",
            pet_response=f"Connected to your TOEFL project {token}. What should we do next?",
            emotion="focused",
        )
        response = self.client.get(reverse("pet"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, token)
        self.assertContains(response, "TOEFL 2026")
        self.assertContains(response, f"open=project%3A{project.pk}")
        self.assertContains(response, "OPEN ↗")
        self.assertContains(response, 'data-object-action="pause"')

    def test_memory_endpoint_is_account_isolated(self):
        PetMemory.objects.create(owner=self.user, memory_type="project", content="My private project", importance=90)
        PetMemory.objects.create(owner=self.other, memory_type="project", content="Someone else's project", importance=99)
        response = self.client.get(reverse("pet_memory"))
        self.assertEqual(response.status_code, 200)
        memories = response.json()["memories"]
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["content"], "My private project")

    def test_chat_validates_method_json_message_and_length(self):
        self.assertEqual(self.client.get(reverse("pet_chat")).status_code, 405)
        self.assertEqual(self.client.post(reverse("pet_chat"), data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(reverse("pet_chat"), data=json.dumps({"message": "  "}), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(reverse("pet_chat"), data=json.dumps({"message": "x" * 1001}), content_type="application/json").status_code, 400)

    @mock.patch("pet.views.run_pet")
    def test_chat_persists_current_conversation_schema(self, mocked_run):
        mocked_run.return_value = {
            "message": "I found your launch task.",
            "emotion": "focused",
            "objects": [{"type": "task", "id": "task_1", "title": "Launch"}],
        }
        response = self.client.post(
            reverse("pet_chat"),
            data=json.dumps({"message": "What should I launch?"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        conversation = PetConversation.objects.get()
        self.assertEqual(conversation.pet, self.pet)
        self.assertIsNotNone(conversation.chat)
        self.assertEqual(conversation.user_message, "What should I launch?")
        self.assertEqual(conversation.pet_response, "I found your launch task.")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.current_state, "focused")

    @mock.patch("pet.agent.brain.ask_nemotron", return_value=None)
    def test_local_fallback_searches_only_the_users_workspace(self, _mocked_nemotron):
        Project.objects.create(owner=self.user, title="Aurora Launch", description="Release project")
        Project.objects.create(owner=self.other, title="Aurora Secret", description="Other account")
        result = run_pet(self.user, "Find the Aurora project")
        self.assertIn("Aurora Launch", result["message"])
        self.assertNotIn("Aurora Secret", result["message"])
        self.assertEqual([item["title"] for item in result["objects"]], ["Aurora Launch"])

    @mock.patch("pet.agent.brain.ask_nemotron")
    def test_explicit_idea_command_creates_and_links_an_idea_without_remote_ai(self, mocked_nemotron):
        result = run_pet(self.user, "Add an idea: build a distraction-free reading mode")

        idea = Idea.objects.get(owner=self.user)
        self.assertEqual(idea.title, "Build a distraction-free reading mode")
        self.assertEqual(idea.status, "inbox")
        self.assertIn(f"[idea:{idea.pk}]", result["message"])
        self.assertEqual(result["objects"][0]["id"], idea.pk)
        self.assertEqual(result["action"]["status"], "created")
        mocked_nemotron.assert_not_called()

    def test_add_this_idea_resolves_the_users_recent_conversation(self):
        PetConversation.objects.create(
            pet=self.pet,
            user_message="What if we build a weekly review dashboard for completed tasks?",
            pet_response="That could turn completed work into a useful progress snapshot.",
            emotion="focused",
        )

        result = run_pet(self.user, "Add this idea")

        idea = Idea.objects.get(owner=self.user)
        self.assertEqual(idea.title, "Build a weekly review dashboard for completed tasks")
        self.assertEqual(result["objects"][0]["type"], "idea")

    def test_add_this_without_history_requests_content_instead_of_creating_blank_item(self):
        result = run_pet(self.user, "Add this task")

        self.assertFalse(Task.objects.filter(owner=self.user).exists())
        self.assertEqual(result["action"]["status"], "needs_input")
        self.assertIn("tell me the task first", result["message"].lower())

        result = run_pet(self.user, "Create an idea.")
        self.assertFalse(Idea.objects.filter(owner=self.user).exists())
        self.assertEqual(result["action"]["status"], "needs_input")

    def test_task_command_applies_user_defaults_due_date_priority_and_owned_project(self):
        settings_obj = UserSettings.objects.create(user=self.user, default_task_duration=30)
        project = Project.objects.create(owner=self.user, title="TOEFL 2026")
        Project.objects.create(owner=self.other, title="Secret Launch")

        result = run_pet(
            self.user,
            "Please add a task to finish the TOEFL 2026 vocabulary review due tomorrow, high priority",
        )

        task = Task.objects.get(owner=self.user)
        self.assertEqual(task.title, "Finish the TOEFL 2026 vocabulary review")
        self.assertEqual(task.project, project)
        self.assertEqual(task.priority, "high")
        self.assertEqual(task.duration_minutes, settings_obj.default_task_duration)
        self.assertEqual(task.due_date, timezone.localdate() + timedelta(days=1))
        self.assertIn(f"[task:{task.pk}]", result["message"])

    def test_chat_api_returns_created_action_and_persists_clickable_reference(self):
        response = self.client.post(
            reverse("pet_chat"),
            data=json.dumps({"message": "Create a task: polish the welcome screen"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        task = Task.objects.get(owner=self.user)
        self.assertEqual(payload["action"]["objectType"], "task")
        self.assertEqual(payload["objects"][0]["id"], task.pk)
        self.assertIn(f"[task:{task.pk}]", PetConversation.objects.get().pet_response)

    @mock.patch("pet.agent.brain.ask_nemotron")
    def test_recent_object_reference_can_be_completed_without_remote_ai(self, mocked_nemotron):
        task = Task.objects.create(owner=self.user, title="Polish the pet cards")
        other_task = Task.objects.create(owner=self.other, title="Other account task")
        PetConversation.objects.create(
            pet=self.pet,
            user_message="Show the pet card task",
            pet_response=f"Here it is. [task:{task.pk}]",
            emotion="focused",
        )

        result = run_pet(self.user, "Mark this done")

        task.refresh_from_db()
        other_task.refresh_from_db()
        self.assertEqual(task.status, "done")
        self.assertIsNotNone(task.completed_on)
        self.assertEqual(other_task.status, "todo")
        self.assertEqual(result["action"]["status"], "updated")
        self.assertEqual(result["objects"][0]["actions"][0]["id"], "reopen")
        mocked_nemotron.assert_not_called()

    def test_ambiguous_object_name_returns_choices_without_mutating(self):
        first = Task.objects.create(owner=self.user, title="Review login flow")
        second = Task.objects.create(owner=self.user, title="Review signup flow")

        result = run_pet(self.user, "Complete review")

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(result["action"]["status"], "ambiguous")
        self.assertEqual(len(result["objects"]), 2)
        self.assertEqual(first.status, "todo")
        self.assertEqual(second.status, "todo")

    def test_project_commands_update_progress_and_status(self):
        project = Project.objects.create(owner=self.user, title="Alpha Launch")

        progress_result = run_pet(self.user, "Set Alpha Launch progress to 60%")
        project.refresh_from_db()
        self.assertEqual(project.progress, 60)
        self.assertEqual(progress_result["objects"][0]["meta"], "ACTIVE · 60%")

        pause_result = run_pet(self.user, "Pause the Alpha Launch project")
        project.refresh_from_db()
        self.assertEqual(project.status, "paused")
        self.assertEqual(pause_result["action"]["status"], "updated")

    def test_idea_can_be_promoted_to_a_linked_project(self):
        idea = Idea.objects.create(
            owner=self.user,
            title="Focus Board",
            description="A calmer daily focus view",
            tags=["focus"],
        )

        result = run_pet(self.user, "Turn the Focus Board idea into a project")

        idea.refresh_from_db()
        project = Project.objects.get(owner=self.user, title="Focus Board")
        self.assertEqual(idea.project, project)
        self.assertEqual(idea.status, "building")
        self.assertEqual([item["type"] for item in result["objects"]], ["project", "idea"])

    def test_collection_commands_return_skills_as_workspace_objects(self):
        skill = Skill.objects.create(owner=self.user, name="UI Reviewer", description="Reviews screens")
        Skill.objects.create(owner=self.other, name="Private Skill")

        result = run_pet(self.user, "Show my skills")

        self.assertEqual(result["action"]["status"], "listed")
        self.assertEqual(len(result["objects"]), 1)
        self.assertEqual(result["objects"][0]["id"], skill.pk)
        self.assertEqual(result["objects"][0]["actions"][0]["id"], "pin")

    def test_object_action_endpoint_updates_owned_object_and_rejects_other_account(self):
        task = Task.objects.create(owner=self.user, title="Ship object actions")
        other_task = Task.objects.create(owner=self.other, title="Private task")

        response = self.client.post(
            reverse("pet_object_action"),
            data=json.dumps({"type": "task", "id": task.pk, "action": "complete"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "done")
        self.assertEqual(response.json()["objects"][0]["actions"][0]["id"], "reopen")

        response = self.client.post(
            reverse("pet_object_action"),
            data=json.dumps({"type": "task", "id": other_task.pk, "action": "complete"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        other_task.refresh_from_db()
        self.assertEqual(other_task.status, "todo")

    def test_project_can_be_created_from_chat(self):
        result = run_pet(self.user, "Create a project: redesign the onboarding flow")

        project = Project.objects.get(owner=self.user)
        self.assertEqual(project.title, "Redesign the onboarding flow")
        self.assertEqual(project.status, "active")
        self.assertEqual(result["objects"][0]["type"], "project")

    def test_new_chat_keeps_old_chat_and_switches_visible_history(self):
        old_chat = PetChatSession.objects.create(pet=self.pet, title="Original plan")
        PetConversation.objects.create(
            pet=self.pet,
            chat=old_chat,
            user_message="Keep this older conversation",
            pet_response="It is safely stored.",
        )

        response = self.client.post(reverse("pet_chat_new"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.pet.chats.count(), 2)
        new_chat = self.pet.chats.exclude(pk=old_chat.pk).get()
        self.assertIn(f"chat={new_chat.pk}", response["Location"])

        new_page = self.client.get(response["Location"])
        self.assertNotContains(new_page, "Keep this older conversation")
        self.assertContains(new_page, "This is a fresh conversation")

        old_page = self.client.get(reverse("pet"), {"chat": old_chat.pk})
        self.assertContains(old_page, "Keep this older conversation")
        self.assertContains(old_page, "Original plan")

    @mock.patch("pet.views.run_pet")
    def test_chat_api_uses_requested_owned_session_and_generates_title(self, mocked_run):
        chat = PetChatSession.objects.create(pet=self.pet)
        mocked_run.return_value = {
            "message": "Ready to help.",
            "emotion": "focused",
            "objects": [],
            "ai": {"status": "online", "provider": "nvidia"},
        }

        response = self.client.post(
            reverse("pet_chat"),
            data=json.dumps({"chatId": str(chat.pk), "message": "Plan the autumn product launch"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        chat.refresh_from_db()
        conversation = PetConversation.objects.get(chat=chat)
        self.assertEqual(chat.title, "Plan the autumn product launch")
        self.assertEqual(response.json()["chatId"], str(chat.pk))
        self.assertEqual(response.json()["chatTitle"], chat.title)
        self.assertEqual(conversation.user_message, "Plan the autumn product launch")
        mocked_run.assert_called_once_with(self.user, "Plan the autumn product launch", chat=chat)

    def test_chat_api_cannot_open_another_users_session(self):
        other_pet = PetProfile.objects.create(owner=self.other, name="Other Voxie")
        other_chat = PetChatSession.objects.create(pet=other_pet, title="Private chat")

        response = self.client.post(
            reverse("pet_chat"),
            data=json.dumps({"chatId": str(other_chat.pk), "message": "Read their chat"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(PetConversation.objects.filter(chat=other_chat).exists())

    @mock.patch("pet.agent.brain.ask_nemotron", return_value="Session-aware response")
    def test_remote_context_contains_only_the_selected_chat(self, mocked_nemotron):
        first_chat = PetChatSession.objects.create(pet=self.pet, title="First")
        second_chat = PetChatSession.objects.create(pet=self.pet, title="Second")
        PetConversation.objects.create(
            pet=self.pet,
            chat=first_chat,
            user_message="FIRST CHAT SECRET",
            pet_response="First reply",
        )
        PetConversation.objects.create(
            pet=self.pet,
            chat=second_chat,
            user_message="SECOND CHAT SECRET",
            pet_response="Second reply",
        )

        run_pet(self.user, "Continue our discussion", chat=first_chat)

        messages = mocked_nemotron.call_args.args[0]
        serialized = json.dumps(messages)
        self.assertIn("FIRST CHAT SECRET", serialized)
        self.assertNotIn("SECOND CHAT SECRET", serialized)

    @mock.patch("pet.agent.brain.ask_nemotron")
    def test_timeout_uses_visible_local_fallback_without_raising(self, mocked_nemotron):
        mocked_nemotron.side_effect = NemotronError(
            "NVIDIA took too long.", code="timeout", retriable=True
        )

        with self.assertLogs("pet.agent.brain", level="WARNING") as logs:
            result = run_pet(self.user, "Help me think through an unlisted challenge")

        self.assertEqual(result["ai"]["status"], "fallback")
        self.assertEqual(result["ai"]["reason"], "timeout")
        self.assertIn("switched to local workspace mode", result["message"])
        self.assertIn("code=timeout", " ".join(logs.output))

    def test_anonymous_pet_api_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("pet_memory"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])


class PetDatabaseToolTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="database-owner", password="test-password-123")
        self.other = User.objects.create_user(username="database-other", password="test-password-123")
        self.pet = PetProfile.objects.create(owner=self.user, name="Voxie")

    def test_queries_and_direct_reads_are_account_isolated(self):
        own = Project.objects.create(owner=self.user, title="Aurora", notes="Private launch notes")
        foreign = Project.objects.create(owner=self.other, title="Aurora Secret")

        result = execute_database_tool(
            self.user,
            "query_records",
            {"object_type": "project", "query": "Aurora"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual([record["id"] for record in result["records"]], [own.pk])
        denied = execute_database_tool(
            self.user,
            "get_record",
            {"object_type": "project", "object_id": foreign.pk},
        )
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["error"]["code"], "not_found")

    def test_complete_record_includes_relationships_but_not_local_paths(self):
        project = Project.objects.create(
            owner=self.user,
            title="Atlas",
            notes="Keep the full decision log here",
            local_path=r"E:\private\atlas",
        )
        task = Task.objects.create(owner=self.user, project=project, title="Ship Atlas")
        settings_obj = UserSettings.objects.create(
            user=self.user,
            workspace_root=r"E:\private",
        )

        result = execute_database_tool(
            self.user,
            "get_record",
            {"object_type": "project", "object_id": project.pk},
        )
        record = result["record"]
        self.assertEqual(record["notes"], "Keep the full decision log here")
        self.assertEqual(record["task_ids"], [task.pk])
        self.assertTrue(record["local_path_configured"])
        self.assertNotIn("local_path", record)

        settings_result = execute_database_tool(
            self.user,
            "get_record",
            {"object_type": "settings", "object_id": "settings"},
        )
        self.assertTrue(settings_result["record"]["local_workspace_boundary_configured"])
        self.assertNotIn("workspace_root", settings_result["record"])
        self.assertEqual(settings_obj.pk, UserSettings.objects.get(user=self.user).pk)

    def test_validated_create_and_update_write_an_activity_audit(self):
        project = Project.objects.create(owner=self.user, title="Launch")

        created = execute_database_tool(
            self.user,
            "create_record",
            {
                "object_type": "task",
                "fields": {
                    "title": "Prepare release notes",
                    "project_id": project.pk,
                    "due_date": "tomorrow",
                    "priority": "high",
                },
            },
            allow_writes=True,
        )

        self.assertTrue(created["ok"])
        task = Task.objects.get(pk=created["record"]["id"])
        self.assertEqual(task.project, project)
        self.assertEqual(task.due_date, timezone.localdate() + timedelta(days=1))
        self.assertEqual(task.priority, "high")

        updated = execute_database_tool(
            self.user,
            "update_record",
            {
                "object_type": "task",
                "object_id": task.pk,
                "fields": {"status": "done", "notes": "Released cleanly"},
            },
            allow_writes=True,
        )
        task.refresh_from_db()
        self.assertTrue(updated["ok"])
        self.assertEqual(task.status, "done")
        self.assertEqual(task.completed_on, timezone.localdate())
        self.assertEqual(
            list(
                Activity.objects.filter(owner=self.user)
                .order_by("pk")
                .values_list("verb", flat=True)
            ),
            ["created", "updated"],
        )

    def test_write_guard_and_foreign_relationship_guard_prevent_mutation(self):
        task = Task.objects.create(owner=self.user, title="Protected task")
        other_project = Project.objects.create(owner=self.other, title="Other project")

        blocked = execute_database_tool(
            self.user,
            "update_record",
            {"object_type": "task", "object_id": task.pk, "fields": {"status": "done"}},
            allow_writes=False,
        )
        task.refresh_from_db()
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["error"]["code"], "write_not_authorized")
        self.assertEqual(task.status, "todo")

        foreign_link = execute_database_tool(
            self.user,
            "update_record",
            {
                "object_type": "task",
                "object_id": task.pk,
                "fields": {"project_id": other_project.pk},
            },
            allow_writes=True,
        )
        task.refresh_from_db()
        self.assertFalse(foreign_link["ok"])
        self.assertIsNone(task.project)

    def test_delete_requires_confirmation_and_logs_the_confirmed_delete(self):
        UserSettings.objects.create(user=self.user, confirm_deletes=True)
        idea = Idea.objects.create(owner=self.user, title="Disposable idea")

        requested = execute_database_tool(
            self.user,
            "delete_record",
            {"object_type": "idea", "object_id": idea.pk, "confirmed": False},
            allow_writes=True,
            delete_authorized=False,
        )
        self.assertTrue(requested["confirmation_required"])
        self.assertTrue(Idea.objects.filter(pk=idea.pk).exists())

        deleted = execute_database_tool(
            self.user,
            "delete_record",
            {"object_type": "idea", "object_id": idea.pk, "confirmed": True},
            allow_writes=True,
            delete_authorized=True,
        )
        self.assertTrue(deleted["ok"])
        self.assertFalse(Idea.objects.filter(pk=idea.pk).exists())
        self.assertTrue(Activity.objects.filter(owner=self.user, verb="deleted").exists())

        active_chat = PetChatSession.objects.create(pet=self.pet, title="Current chat")
        blocked_chat = execute_database_tool(
            self.user,
            "delete_record",
            {"object_type": "chat", "object_id": str(active_chat.pk), "confirmed": True},
            allow_writes=True,
            delete_authorized=True,
            active_chat=active_chat,
        )
        self.assertFalse(blocked_chat["ok"])
        self.assertEqual(blocked_chat["error"]["code"], "active_chat")
        self.assertTrue(PetChatSession.objects.filter(pk=active_chat.pk).exists())

    def test_task_dependency_cycles_are_rejected(self):
        first = Task.objects.create(owner=self.user, title="First")
        second = Task.objects.create(owner=self.user, title="Second", depends_on=first)

        result = execute_database_tool(
            self.user,
            "update_record",
            {
                "object_type": "task",
                "object_id": first.pk,
                "fields": {"depends_on_id": second.pk},
            },
            allow_writes=True,
        )

        first.refresh_from_db()
        self.assertFalse(result["ok"])
        self.assertIn("cycle", result["error"]["message"])
        self.assertIsNone(first.depends_on)

    def test_old_chat_messages_are_searchable_without_cross_account_leaks(self):
        chat = PetChatSession.objects.create(pet=self.pet, title="Archive")
        own_message = PetConversation.objects.create(
            pet=self.pet,
            chat=chat,
            user_message="ARCHIVE-CODE belongs to me",
            pet_response="Stored safely",
        )
        other_pet = PetProfile.objects.create(owner=self.other, name="Other")
        other_chat = PetChatSession.objects.create(pet=other_pet, title="Private")
        PetConversation.objects.create(
            pet=other_pet,
            chat=other_chat,
            user_message="ARCHIVE-CODE from someone else",
            pet_response="Private",
        )

        result = execute_database_tool(
            self.user,
            "query_records",
            {"object_type": "message", "query": "ARCHIVE-CODE"},
        )
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["records"][0]["id"], str(own_message.pk))
        self.assertNotIn("someone else", json.dumps(result))

    @mock.patch("pet.agent.brain.ask_nemotron")
    def test_agent_executes_database_tool_loop_and_returns_object_card(self, mocked_nemotron):
        task = Task.objects.create(
            owner=self.user,
            title="Pay overdue invoice",
            due_date=timezone.localdate() - timedelta(days=1),
        )
        mocked_nemotron.side_effect = [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_overdue",
                        "type": "function",
                        "function": {
                            "name": "query_records",
                            "arguments": json.dumps(
                                {"object_type": "task", "due": "overdue", "limit": 5}
                            ),
                        },
                    }
                ],
            },
            {"content": "The overdue invoice deserves attention first.", "tool_calls": []},
        ]

        result = run_pet(self.user, "Help me decide what deserves attention today")

        self.assertEqual(mocked_nemotron.call_count, 2)
        second_messages = mocked_nemotron.call_args_list[1].args[0]
        tool_message = next(item for item in second_messages if item["role"] == "tool")
        self.assertIn(task.pk, tool_message["content"])
        self.assertEqual(result["objects"][0]["id"], task.pk)
        self.assertIn(f"[task:{task.pk}]", result["message"])
        self.assertEqual(result["ai"]["toolsUsed"], ["query_records"])


class PetModelTests(TestCase):
    def test_write_intent_guard_rejects_questions_and_negation(self):
        self.assertTrue(_explicit_write_intent("Can you update the task?"))
        self.assertFalse(_explicit_write_intent("Do not update the task"))
        self.assertFalse(_explicit_write_intent("What should I update?"))
        self.assertFalse(_explicit_write_intent("Show me how to update a task"))

    def test_unassigned_profile_string_is_safe(self):
        pet = PetProfile.objects.create(owner=None, name="Orphan")
        self.assertEqual(str(pet), "Orphan (unassigned)")

    def test_large_xp_gain_applies_every_earned_level(self):
        pet = PetProfile.objects.create(owner=None, name="Leveler", level=1, xp=0)
        add_xp(pet, 250)
        pet.refresh_from_db()
        self.assertEqual(pet.level, 3)
        self.assertEqual(pet.xp, 250)


class NvidiaClientTests(SimpleTestCase):
    class StreamingResponse:
        headers = {"Content-Type": "text/event-stream; charset=utf-8"}

        def __init__(self):
            self.lines = [
                b'data: {"choices":[{"delta":{"content":"Hello "}}]}\n',
                b'data: {"choices":[{"delta":{"content":"workspace"}}]}\n',
                b"data: [DONE]\n",
            ]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def __iter__(self):
            return iter(self.lines)

    class JsonResponse:
        headers = {"Content-Type": "application/json"}

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    @mock.patch.dict(
        os.environ,
        {
            "NVIDIA_API_KEY": "test-key",
            "PET_AGENT_RETRIES": "0",
            "PET_AGENT_STREAM": "1",
            "PET_AGENT_MAX_TOKENS": "321",
        },
    )
    @mock.patch("pet.agent.nvidia.urllib.request.urlopen")
    def test_streamed_completion_is_assembled_and_bounded(self, mocked_urlopen):
        mocked_urlopen.return_value = self.StreamingResponse()

        reply = ask_nemotron([{"role": "user", "content": "Hello"}])

        self.assertEqual(reply, "Hello workspace")
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["max_tokens"], 321)
        self.assertNotIn("test-key", request.data.decode("utf-8"))

    @mock.patch.dict(
        os.environ,
        {"NVIDIA_API_KEY": "test-key", "PET_AGENT_RETRIES": "1", "PET_AGENT_TIMEOUT_SECONDS": "12"},
    )
    @mock.patch("pet.agent.nvidia.time.sleep")
    @mock.patch("pet.agent.nvidia.urllib.request.urlopen", side_effect=TimeoutError("slow"))
    def test_timeout_retries_once_then_returns_typed_error(self, mocked_urlopen, mocked_sleep):
        with self.assertRaises(NemotronError) as context:
            ask_nemotron([{"role": "user", "content": "Hello"}])

        self.assertEqual(context.exception.code, "timeout")
        self.assertEqual(mocked_urlopen.call_count, 2)
        mocked_sleep.assert_called_once()

    @mock.patch.dict(
        os.environ,
        {
            "NVIDIA_API_KEY": "test-key",
            "PET_AGENT_RETRIES": "0",
            "PET_AGENT_STREAM": "1",
            "PET_AGENT_THINKING": "0",
        },
    )
    @mock.patch("pet.agent.nvidia.urllib.request.urlopen")
    def test_tool_call_response_is_structured_and_disables_streaming(self, mocked_urlopen):
        mocked_urlopen.return_value = self.JsonResponse(
            {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "workspace_overview",
                                        "arguments": "{}",
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        )
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "workspace_overview",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        response = ask_nemotron(
            [{"role": "user", "content": "Summarize my workspace"}],
            tools=tools,
            tool_choice="auto",
        )

        self.assertEqual(response["tool_calls"][0]["function"]["name"], "workspace_overview")
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["tools"], tools)
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertFalse(payload["chat_template_kwargs"]["enable_thinking"])
