import gradio as gr
import random
import logging
from config import API_BASE_URL, API_KEY
from constants import THEME_LIST, TRAIT_LIST, CHARACTER_NAME_LIST, STORY_TITLE_LIST
from utils.http_client import create_sync_client

API_BASE = API_BASE_URL
logger = logging.getLogger(__name__)


def get_random_theme():
    """Get a random theme from the list"""
    return random.choice(THEME_LIST)


def get_random_character_name():
    """Get a random character name from the list"""
    return random.choice(CHARACTER_NAME_LIST)


def get_random_story_title():
    """Get a random story title from the list"""
    return random.choice(STORY_TITLE_LIST)


def get_random_traits():
    """Get 2-3 random traits from the list"""
    num_traits = random.randint(2, 3)
    return random.sample(TRAIT_LIST, num_traits)


def create_user_and_start(
    username: str,
    character_name: str,
    title: str,
    theme_mode: str,
    theme_dropdown: str,
    theme_custom: str,
    traits: list,
    custom_traits: str,
    model: str,
):
    """Create user and start a new story session with smart theme selection"""
    # Determine final theme based on mode
    if "Random" in theme_mode:
        final_theme = get_random_theme()
    elif "List" in theme_mode:
        final_theme = theme_dropdown
    else:  # Custom
        final_theme = theme_custom if theme_custom.strip() else "An adventure begins"

    # Convert traits list to proper format and add custom traits
    traits_list = traits if isinstance(traits, list) else []

    # Add custom traits if provided
    if custom_traits and custom_traits.strip():
        custom_list = [t.strip() for t in custom_traits.split(",") if t.strip()]
        traits_list.extend(custom_list)

    try:
        with create_sync_client(API_KEY) as client:
            # Create user
            r = client.post(f"{API_BASE}/api/user", json={"username": username})
            r.raise_for_status()
            user = r.json()

            # Start session
            r2 = client.post(
                f"{API_BASE}/api/session/start",
                json={
                    "user_id": user["id"],
                    "title": title,
                    "theme": final_theme,
                    "traits": traits_list,
                    "character_name": character_name or username,
                    "model": (model or "").lower() or None,
                },
            )
            r2.raise_for_status()
            sess = r2.json()

            first_choice = sess["choices"][0] if sess["choices"] else None

            # Handle clues - extract clean text
            clues_raw = sess.get("clues", "")
            if isinstance(clues_raw, dict):
                clues_text = (
                    clues_raw.get("text", "")
                    or clues_raw.get("clues", "")
                    or "No clues yet..."
                )
            elif isinstance(clues_raw, str):
                clues_text = (
                    clues_raw.strip() if clues_raw.strip() else "No clues yet..."
                )
            else:
                clues_text = "No clues yet..."

            # Format clues nicely
            if clues_text and clues_text != "No clues yet...":
                clues_text = f"🔍 {clues_text}"

            # Show what theme was actually used (especially for random)
            theme_display = (
                f"🎨 **Theme Generated:** {final_theme}"
                if "Random" in theme_mode
                else ""
            )

            return (
                f"✅ Session {sess['session_id']} started for {user['username']}!\n"
                f"Character: {character_name or username}\n"
                f"Theme: {final_theme[:60]}...\n"
                f"Traits: {', '.join(traits_list)}",
                sess["session_id"],
                sess["narration"],
                gr.update(choices=sess["choices"], value=first_choice),
                clues_text,
                theme_display,  # Return the generated theme display
            )
    except Exception as e:
        return (
            f"❌ Error: {str(e)}",
            0,
            "Failed to start session. Make sure the API server is running.",
            gr.update(choices=["Error"], value=None),
            "",
            "",  # Empty theme display on error
        )


def do_step(
    session_id: int,
    input_mode: str,
    user_input: str,
    choice_value: str | None,
    model: str,
):
    """Advance the story based on selected input mode (button choices OR custom text)"""
    if not session_id or session_id == 0:
        return (
            "⚠️ Please start a session first!",
            gr.update(choices=["Start a session first"], value=None),
            "",
            "",  # Clear custom input
        )

    try:
        choice_idx = None
        final_user_input = None

        with create_sync_client(API_KEY) as client:
            # Use the selected input mode
            if input_mode == "buttons":
                # Button mode - use selected choice
                if (
                    choice_value
                    and choice_value != "None"
                    and choice_value != "Start a session first"
                    and choice_value != "⏳ Waiting for story to begin..."
                ):
                    final_user_input = choice_value
                    choice_idx = None
                else:
                    return ("⚠️ Please select a choice button!", gr.update(), "", "")
            else:  # custom mode
                # Custom text mode - use typed input
                if user_input and user_input.strip():
                    final_user_input = user_input.strip()
                    choice_idx = None
                else:
                    return ("⚠️ Please type your custom action!", gr.update(), "", "")

            # Prepare payload (only send one: choice_index OR user_input)
            payload = {
                "user_input": final_user_input,
                "choice_index": choice_idx,
                "model": (model or "").lower() or None,
            }

            # Make the step request
            r = client.post(
                f"{API_BASE}/api/session/{int(session_id)}/step", json=payload
            )

            # Handle 409 Conflict (already processing)
            if r.status_code == 409:
                return (
                    "⏳ **Story is being generated...**\n\nPlease wait for the current generation to complete before making another choice.",
                    gr.update(),
                    "⏳ Processing...",
                    "",
                )

            r.raise_for_status()
            d = r.json()

            first_choice = d.get("choices", [None])[0] if d.get("choices") else None

            # Handle clues - extract clean text
            clues_raw = d.get("clues", "")
            if isinstance(clues_raw, dict):
                clues_text = (
                    clues_raw.get("text", "")
                    or clues_raw.get("clues", "")
                    or "No new clues..."
                )
            elif isinstance(clues_raw, str):
                clues_text = (
                    clues_raw.strip() if clues_raw.strip() else "No new clues..."
                )
            else:
                clues_text = "No new clues..."

            # Format clues nicely
            if clues_text and clues_text != "No new clues...":
                clues_text = f"🔍 {clues_text}"

            return (
                d["narration"],
                gr.update(choices=d.get("choices", []), value=first_choice),
                clues_text,
                "",  # Clear custom input after successful step
            )
    except Exception as e:
        error_msg = str(e)
        # Check if it's a 409 error in the exception message
        if "409" in error_msg or "already processing" in error_msg.lower():
            return (
                "⏳ **Story is being generated...**\n\nPlease wait for the current generation to complete before making another choice.",
                gr.update(),
                "⏳ Processing...",
                "",
            )
        return (
            f"❌ Error: {error_msg}",
            gr.update(choices=["Error"], value=None),
            "",
            "",
        )


def save_session(session_id: int, save_title: str):
    """
    Create a new save with a custom title.
    Like saving your game in a specific slot.
    """
    if not session_id or session_id == 0:
        return "⚠️ No active session to save.", None

    if not save_title or not save_title.strip():
        save_title = f"Quick Save"

    try:
        with create_sync_client(API_KEY) as client:
            r = client.post(
                f"{API_BASE}/api/session/{int(session_id)}/save",
                json={"title": save_title.strip(), "description": ""},
            )
            r.raise_for_status()
            d = r.json()

            # Return success message and updated saves list
            message = (
                f"💾 **Save Created!**\n"
                f"📝 Name: {d.get('title')}\n"
                f"🎯 Step: {d.get('current_step')}\n"
                f"🆔 ID: #{d.get('snapshot_id')}"
            )

            # Refresh the saves list
            saves_list = get_saves_list(session_id)
            return message, saves_list
    except Exception as e:
        return f"❌ Save failed: {str(e)}", None


def get_saves_list(session_id: int):
    """
    Get all saves for the current session.
    Returns a list of save choices for the dropdown.
    """
    if not session_id or session_id == 0:
        return []

    try:
        with create_sync_client(API_KEY) as client:
            r = client.get(f"{API_BASE}/api/session/{int(session_id)}/snapshots")
            r.raise_for_status()
            data = r.json()
            snapshots = data.get("snapshots", [])

            if not snapshots:
                return ["No saves available"]

            # Format: "Save Name (Step X) - Created: timestamp"
            choices = []
            for snap in snapshots:
                title = snap.get("title", "Untitled")
                step = snap.get("current_step", 0)
                created = snap.get("created_at", "")[:19]  # Trim to datetime only
                snap_id = snap.get("id")

                # Format: "Save Name (Step 5) - 2024-01-15 14:30:00 [ID: 3]"
                choice_text = f"{title} (Step {step}) - {created} [ID: {snap_id}]"
                choices.append(choice_text)

            return choices
    except Exception as e:
        logger.error(f"Failed to get saves list: {e}")
        return ["Error loading saves"]


def load_selected_save(session_id: int, selected_save: str):
    """
    Load a specific save from the dropdown selection.
    Extracts the snapshot ID from the selection and loads it.
    """
    if not session_id or session_id == 0:
        return "⚠️ No active session.", "", None, ""

    if (
        not selected_save
        or selected_save == "No saves available"
        or selected_save == "Error loading saves"
    ):
        return "⚠️ Please select a save to load.", "", None, ""

    try:
        # Extract snapshot ID from the selection text
        # Format: "Save Name (Step 5) - 2024-01-15 14:30:00 [ID: 3]"
        import re

        match = re.search(r"\[ID: (\d+)\]", selected_save)
        if not match:
            return "❌ Invalid save selection.", "", None, ""

        snapshot_id = int(match.group(1))

        with create_sync_client(API_KEY) as client:
            # Load the snapshot
            r = client.post(
                f"{API_BASE}/api/session/{int(session_id)}/load/{snapshot_id}"
            )
            r.raise_for_status()
            d = r.json()

            # Get narration and choices from world_state (not history!)
            # The snapshot preserves the exact narration and choices from the save point
            world_state = d.get("world_state", {})
            last_narration = world_state.get("last_narration", "")
            last_choices = world_state.get("last_choices", [])

            message = (
                f"📂 **Game Loaded!**\n"
                f"✅ {d.get('message', 'Save loaded successfully')}\n"
                f"🎯 Restored to Step: {d.get('current_step')}\n\n"
                f"You can now make a different choice at this point!"
            )

            # Return: message, narration, choices update, clues
            # Show the actual choices from the loaded state
            if last_choices:
                choices_update = gr.update(choices=last_choices, value=None)
            else:
                choices_update = gr.update(
                    choices=["Continue from here..."], value=None
                )

            return (
                message,
                last_narration,
                choices_update,
                "🔄 Game state restored. Make your choice!",
            )
    except Exception as e:
        return f"❌ Load failed: {str(e)}", "", None, ""


def delete_selected_save(session_id: int, selected_save: str):
    """
    Delete a specific save.
    """
    if not session_id or session_id == 0:
        return "⚠️ No active session.", None

    if (
        not selected_save
        or selected_save == "No saves available"
        or selected_save == "Error loading saves"
    ):
        return "⚠️ Please select a save to delete.", None

    try:
        # Extract snapshot ID
        import re

        match = re.search(r"\[ID: (\d+)\]", selected_save)
        if not match:
            return "❌ Invalid save selection.", None

        snapshot_id = int(match.group(1))

        with create_sync_client(API_KEY) as client:
            r = client.delete(f"{API_BASE}/api/snapshot/{snapshot_id}")
            r.raise_for_status()

            message = f"🗑️ Save deleted successfully!"

            # Refresh the saves list
            saves_list = get_saves_list(session_id)
            return message, saves_list
    except Exception as e:
        return f"❌ Delete failed: {str(e)}", None


def rename_selected_save(session_id: int, selected_save: str, new_name: str):
    """
    Rename a specific save.
    """
    if not session_id or session_id == 0:
        return "⚠️ No active session.", None

    if (
        not selected_save
        or selected_save == "No saves available"
        or selected_save == "Error loading saves"
    ):
        return "⚠️ Please select a save to rename.", None

    if not new_name or not new_name.strip():
        return "⚠️ Please enter a new name.", None

    try:
        # Extract snapshot ID
        import re

        match = re.search(r"\[ID: (\d+)\]", selected_save)
        if not match:
            return "❌ Invalid save selection.", None

        snapshot_id = int(match.group(1))

        with create_sync_client(API_KEY) as client:
            r = client.put(
                f"{API_BASE}/api/snapshot/{snapshot_id}/rename",
                json={"new_title": new_name.strip()},
            )
            r.raise_for_status()

            message = f"✏️ Save renamed to: {new_name}"

            # Refresh the saves list
            saves_list = get_saves_list(session_id)
            return message, saves_list
    except Exception as e:
        return f"❌ Rename failed: {str(e)}", None


def _healthcheck_text():
    try:
        with create_sync_client(API_KEY) as client:
            r = client.get(f"{API_BASE}/api/health")
            if r.status_code == 200:
                return f"✅ API OK: {API_BASE}"
            return f"⚠️ API reachable but returned {r.status_code}"
    except Exception as e:
        return f"❌ API unreachable at {API_BASE}: {e}"


with gr.Blocks(
    # Keep the Soft layout while making labels, hints and selected controls readable.
    theme=gr.themes.Soft().set(
        block_label_text_color="#4338ca",
        block_label_text_color_dark="#e2e8f0",
        block_info_text_color="#4b5563",
        block_info_text_color_dark="#cbd5e1",
        block_title_text_color="#4338ca",
        block_title_text_color_dark="#e2e8f0",
        body_text_color_subdued="#4b5563",
        body_text_color_subdued_dark="#cbd5e1",
        checkbox_label_background_fill_selected="#4338ca",
        checkbox_label_background_fill_selected_dark="#3730a3",
        checkbox_label_text_color_selected="#ffffff",
        checkbox_label_text_color_selected_dark="#ffffff",
        button_primary_background_fill="#4338ca",
        button_primary_background_fill_hover="#3730a3",
        button_primary_background_fill_dark="#4338ca",
        button_primary_background_fill_hover_dark="#3730a3",
        button_primary_border_color="#4338ca",
        button_primary_border_color_hover="#3730a3",
        button_primary_border_color_dark="#4338ca",
        button_primary_border_color_hover_dark="#3730a3",
        button_primary_text_color="#ffffff",
        button_primary_text_color_dark="#ffffff",
    ),
    title="🎭 Interactive Story Game - Your Adventure Awaits",
    css="""
        /* Make narration text BIGGER and more readable */
        #narration_display textarea {
            font-size: 18px !important;
            line-height: 1.8 !important;
            font-family: 'Georgia', 'Times New Roman', serif !important;
            padding: 20px !important;
        }

        /* Make choices text bigger */
        #choices_display label {
            font-size: 16px !important;
            line-height: 1.6 !important;
        }

        /* Make clues text bigger */
        #clues_display textarea {
            font-size: 16px !important;
            line-height: 1.7 !important;
        }

        /* Make custom input bigger */
        #custom_input textarea {
            font-size: 16px !important;
            line-height: 1.6 !important;
        }
    """,
) as demo:
    gr.Markdown(
        """
        # 🎭 Interactive Story Game

        ## ✨ Create Your Own AI-Powered Adventure Story!

        **Simple Steps:** Create Character → Choose Theme → Start Playing → Make Choices → Watch Your Story Unfold
        """
    )

    # API Status in a compact accordion
    with gr.Accordion("🔧 System Status", open=False):
        api_info = gr.Markdown(_healthcheck_text())

    # Hidden state for session ID (shared across all tabs)
    session_id_box = gr.Number(label="Session ID", value=0, visible=False)

    with gr.Tabs() as tabs:
        with gr.Tab("🎮 Play Story"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("## 🎬 Setup Your Adventure")

                    # Character Setup in Accordion
                    with gr.Accordion("👤 Step 1: Character Setup", open=True):
                        username = gr.Textbox(
                            label="👤 Username",
                            value="player1",
                            placeholder="Your username",
                            info="Your player name",
                        )
                        with gr.Row():
                            character_name = gr.Dropdown(
                                label="🎭 Character Name",
                                choices=CHARACTER_NAME_LIST,
                                value="Alex",
                                allow_custom_value=True,
                                info="Choose a preset or type your own",
                                scale=3,
                            )
                            random_name_btn = gr.Button("🎲 Random", scale=1, size="sm")
                        with gr.Row():
                            title = gr.Dropdown(
                                label="📚 Story Title",
                                choices=STORY_TITLE_LIST,
                                value="The Legend of the Lost Kingdom",
                                allow_custom_value=True,
                                info="Choose a preset or type your own",
                                scale=3,
                            )
                            random_title_btn = gr.Button(
                                "🎲 Random", scale=1, size="sm"
                            )

                    # Theme Setup in Accordion
                    with gr.Accordion("🎨 Step 2: Choose Your World", open=True):
                        theme_mode = gr.Radio(
                            choices=[
                                "🎲 Random Theme",
                                "📋 Choose from List",
                                "✍️ Custom Theme",
                            ],
                            value="📋 Choose from List",
                            label="How do you want to choose?",
                            info="Pick your preferred method",
                        )
                        theme_dropdown = gr.Dropdown(
                            choices=THEME_LIST,
                            value=THEME_LIST[0],
                            label="📋 Select a Theme",
                            visible=True,
                            info="Choose from our curated themes",
                        )
                        theme = gr.Textbox(
                            label="✍️ Write Your Own Theme",
                            value="",
                            placeholder="Describe your own world... (e.g., 'A steampunk city with flying ships')",
                            lines=2,
                            visible=False,
                            info="Be creative! Describe any world you can imagine",
                        )
                        random_theme_btn = gr.Button(
                            "🎲 Generate Random Theme", visible=False
                        )

                        # Display what theme was generated (for random themes)
                        generated_theme_display = gr.Markdown(value="", visible=True)

                    # Traits Setup in Accordion
                    with gr.Accordion("⭐ Step 3: Character Personality", open=True):
                        with gr.Row():
                            gr.Markdown("**Choose traits that define your character:**")
                            random_traits_btn = gr.Button(
                                "🎲 Random Traits", size="sm", scale=0
                            )
                        traits = gr.CheckboxGroup(
                            choices=TRAIT_LIST,
                            value=["Brave", "Curious"],
                            label="Quick Select Traits",
                            info="Pick from common traits",
                        )
                        custom_traits = gr.Textbox(
                            label="✍️ Add Your Own Traits",
                            placeholder="Type custom traits separated by commas (e.g., 'Mysterious, Witty, Adventurous')",
                            info="Add any traits you want! Separate with commas",
                        )

                    # AI Model in Accordion
                    with gr.Accordion("🤖 Step 4: AI Settings", open=False):
                        model_selector = gr.Dropdown(
                            label="🤖 Choose AI Model",
                            choices=[
                                ("🖥️ Local AI (LM Studio) - Fast & Private", "local"),
                                ("☁️ Online AI (Hugging Face) - Cloud-Based", "hf"),
                            ],
                            value="local",
                            info="Local = Faster, Online = More variety",
                        )

                    # Big Start Button
                    gr.Markdown("---")
                    start_btn = gr.Button(
                        "🚀 START MY ADVENTURE!", variant="primary", size="lg"
                    )
                    start_info = gr.Textbox(
                        label="📢 Status", interactive=False, show_label=False
                    )

                    # Hidden state
                    session_id_box = gr.Number(
                        label="Session ID", value=0, visible=False
                    )
                    current_choices_state = gr.State(value=[])

                    # Session Controls in Accordion
                    gr.Markdown("---")
                    with gr.Accordion("💾 Save & Load Game", open=False):
                        gr.Markdown("### 💾 Create New Save")
                        with gr.Row():
                            save_title_input = gr.Textbox(
                                label="Save Name",
                                placeholder="e.g., 'Before Dragon Fight', 'Chapter 2 Start'",
                                value="Quick Save",
                                scale=3,
                            )
                            save_btn = gr.Button(
                                "💾 Save Now", variant="primary", scale=1
                            )

                        gr.Markdown("### 📂 Load Existing Save")
                        saves_dropdown = gr.Dropdown(
                            label="Your Saves",
                            choices=["No saves available"],
                            value=None,
                            interactive=True,
                            info="Select a save to load, rename, or delete",
                        )
                        with gr.Row():
                            load_btn = gr.Button(
                                "📂 Load Selected", variant="primary", scale=1
                            )
                            refresh_saves_btn = gr.Button("🔄 Refresh List", scale=1)

                        gr.Markdown("### ✏️ Manage Saves")
                        with gr.Row():
                            rename_input = gr.Textbox(
                                label="New Name",
                                placeholder="Enter new save name",
                                scale=2,
                            )
                            rename_btn = gr.Button("✏️ Rename", scale=1)
                            delete_btn = gr.Button("🗑️ Delete", variant="stop", scale=1)

                        save_load_status = gr.Markdown(value="", label="Status")

                with gr.Column(scale=2):
                    gr.Markdown("## 📖 Your Story")

                    # Story Display (BIGGER for better readability)
                    narration_out = gr.Textbox(
                        label="📜 Current Scene",
                        lines=15,
                        max_lines=25,
                        interactive=False,
                        placeholder="✨ Your adventure will begin here...\n\n👈 Fill in the setup on the left and click 'START MY ADVENTURE!' to begin your story!",
                        show_label=True,
                        elem_id="narration_display",
                    )

                    gr.Markdown("---")
                    gr.Markdown("## 🎯 Your Turn - What Will You Do?")

                    # Input mode selector - choose between buttons or custom text
                    input_mode_selector = gr.Radio(
                        choices=["🎲 Use Button Choices", "✍️ Write Custom Action"],
                        value="🎲 Use Button Choices",
                        label="Choose How to Play This Turn:",
                        info="Switch between guided choices or free-form actions anytime!",
                    )

                    # Button choices area
                    choices_box = gr.Radio(
                        choices=["⏳ Waiting for story to begin..."],
                        value=None,
                        label="🎲 Click a Choice:",
                        info="Pick one of the options below",
                        visible=True,
                        elem_id="choices_display",
                    )

                    # Custom text area (BIGGER for longer inputs)
                    free_input = gr.Textbox(
                        label="✍️ Type Your Action:",
                        placeholder="What do you do? Be creative! (e.g., 'I examine the door carefully' or 'I talk to the stranger')",
                        lines=5,
                        max_lines=8,
                        info="Write anything you want your character to do!",
                        visible=False,
                        elem_id="custom_input",
                    )

                    # Action button
                    go_btn = gr.Button("▶️ CONTINUE STORY", variant="primary", size="lg")

                    # Clues section in accordion (BIGGER)
                    with gr.Accordion("🔍 Clues & Discoveries", open=True):
                        clues_box = gr.Textbox(
                            label="",
                            lines=4,
                            max_lines=6,
                            interactive=False,
                            placeholder="🕵️ Hidden clues and secrets will appear here as you explore...",
                            show_label=False,
                            elem_id="clues_display",
                        )

                    # Summary section in accordion
                    with gr.Accordion("📝 Scene Summary", open=False):
                        summary_btn = gr.Button(
                            "✨ Generate Summary", variant="secondary"
                        )
                        summary_out = gr.Textbox(
                            label="",
                            lines=5,
                            interactive=False,
                            placeholder="Click 'Generate Summary' to get a brief summary of the current scene...",
                            show_label=False,
                        )

    # Input mode selector handler - toggle between buttons and custom text
    def update_input_visibility(mode):
        if "Button" in mode:
            return gr.update(visible=True), gr.update(visible=False)
        else:  # Custom
            return gr.update(visible=False), gr.update(visible=True)

    input_mode_selector.change(
        update_input_visibility,
        inputs=[input_mode_selector],
        outputs=[choices_box, free_input],
    )

    # Theme mode change handler
    def update_theme_visibility(mode):
        if "Random" in mode:
            return (
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
            )
        elif "List" in mode:
            return (
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
            )
        else:  # Custom
            return (
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=False),
            )

    theme_mode.change(
        update_theme_visibility,
        inputs=[theme_mode],
        outputs=[theme_dropdown, theme, random_theme_btn],
    )

    # Random theme button handler
    def set_random_theme():
        return get_random_theme()

    random_theme_btn.click(set_random_theme, inputs=[], outputs=[theme])

    # Random character name button handler
    def set_random_character_name():
        return get_random_character_name()

    random_name_btn.click(
        set_random_character_name, inputs=[], outputs=[character_name]
    )

    # Random story title button handler
    def set_random_story_title():
        return get_random_story_title()

    random_title_btn.click(set_random_story_title, inputs=[], outputs=[title])

    # Random traits button handler
    def set_random_traits():
        return get_random_traits()

    random_traits_btn.click(set_random_traits, inputs=[], outputs=[traits])

    def _wrap_start(
        username,
        character_name,
        title,
        theme_mode,
        theme_dropdown,
        theme_custom,
        traits,
        custom_traits_input,
        model,
    ):
        status, session_id, narration, choices_update, clues, theme_display = (
            create_user_and_start(
                username,
                character_name,
                title,
                theme_mode,
                theme_dropdown,
                theme_custom,
                traits,
                custom_traits_input,
                model,
            )
        )
        # Store current choices in hidden state for mapping later
        return (
            status,
            session_id,
            narration,
            choices_update,
            clues,
            choices_update["choices"] if isinstance(choices_update, dict) else [],
            theme_display,
        )

    start_btn.click(
        _wrap_start,
        inputs=[
            username,
            character_name,
            title,
            theme_mode,
            theme_dropdown,
            theme,
            traits,
            custom_traits,
            model_selector,
        ],
        outputs=[
            start_info,
            session_id_box,
            narration_out,
            choices_box,
            clues_box,
            current_choices_state,
            generated_theme_display,
        ],
    )

    def _wrap_step(
        session_id, input_mode, free_input_value, selected_choice, stored_choices, model
    ):
        # Convert input mode to simple string
        mode = "buttons" if "Button" in input_mode else "custom"
        # Call do_step which now returns 4 values (including cleared input)
        narration, choices_update, clues, cleared_input = do_step(
            session_id, mode, free_input_value, selected_choice, model
        )
        new_choices = (
            choices_update.get("choices", [])
            if isinstance(choices_update, dict)
            else []
        )
        return narration, choices_update, clues, new_choices, cleared_input

    go_btn.click(
        _wrap_step,
        inputs=[
            session_id_box,
            input_mode_selector,
            free_input,
            choices_box,
            current_choices_state,
            model_selector,
        ],
        outputs=[
            narration_out,
            choices_box,
            clues_box,
            current_choices_state,
            free_input,
        ],
    )

    # Save button - creates new save with custom name
    save_btn.click(
        save_session,
        inputs=[session_id_box, save_title_input],
        outputs=[save_load_status, saves_dropdown],
    )

    # Load button - loads the selected save
    load_btn.click(
        load_selected_save,
        inputs=[session_id_box, saves_dropdown],
        outputs=[save_load_status, narration_out, choices_box, clues_box],
    )

    # Refresh button - updates the saves list
    refresh_saves_btn.click(
        lambda sid: gr.update(choices=get_saves_list(sid)),
        inputs=[session_id_box],
        outputs=[saves_dropdown],
    )

    # Rename button - renames the selected save
    rename_btn.click(
        rename_selected_save,
        inputs=[session_id_box, saves_dropdown, rename_input],
        outputs=[save_load_status, saves_dropdown],
    )

    # Delete button - deletes the selected save
    delete_btn.click(
        delete_selected_save,
        inputs=[session_id_box, saves_dropdown],
        outputs=[save_load_status, saves_dropdown],
    )

    def summarize_scene(session_id: int, current_narration: str, model: str):
        """Generate a summary of the current scene"""
        if not session_id or session_id == 0:
            return "⚠️ No active session. Please start a story first!"
        if (
            not current_narration
            or current_narration.strip() == ""
            or "adventure will begin here" in current_narration.lower()
        ):
            return "⚠️ No scene to summarize yet. Play through the story first!"
        try:
            with create_sync_client(API_KEY) as client:
                r = client.post(
                    f"{API_BASE}/api/session/{int(session_id)}/summarize",
                    json={
                        "text": current_narration,
                        "model": (model or "").lower() or None,
                    },
                )
                r.raise_for_status()
                data = r.json()

                # Extract just the summary text from the response
                if isinstance(data, dict) and "summary" in data:
                    summary_text = data["summary"]
                elif isinstance(data, str):
                    summary_text = data
                else:
                    summary_text = str(data)

                # Clean up the summary text
                summary_text = summary_text.strip()

                # Remove any "Summary:" prefix if the AI added it
                if summary_text.lower().startswith("summary:"):
                    summary_text = summary_text[8:].strip()

                return f"✨ {summary_text}"
        except Exception as e:
            return f"❌ Summary generation failed: {str(e)}"

    summary_btn.click(
        summarize_scene,
        inputs=[session_id_box, narration_out, model_selector],
        outputs=[summary_out],
    )

    with tabs:
        with gr.Tab("📖 Story History"):
            gr.Markdown(
                """
                ### 📚 Your Complete Adventure

                **View your entire story from beginning to current point!**
                - Click "🔄 Refresh Story" to load your full adventure
                - Click "💾 Download as Text" to save your story to a file
                - Perfect for reviewing your journey and past choices
                """
            )

            with gr.Row():
                refresh_story_btn = gr.Button(
                    "🔄 Refresh Story", variant="primary", size="lg"
                )
                download_story_btn = gr.Button(
                    "💾 Download as Text", variant="secondary", size="lg"
                )

            story_display = gr.Textbox(
                label="Full Story",
                lines=25,
                max_lines=40,
                interactive=False,
                placeholder="Your complete story will appear here...\n\nClick 'Refresh Story' to load your adventure!",
                show_label=False,
            )

            download_file_output = gr.File(label="📥 Your Story File")

            def load_full_story(session_id: int):
                if not session_id or session_id == 0:
                    return "⚠️ No active session. Start a story first!"
                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.get(
                            f"{API_BASE}/api/session/{int(session_id)}/story-full"
                        )
                        r.raise_for_status()
                        response = r.json()

                        # Handle both direct dict and wrapped responses
                        if isinstance(response, dict):
                            data = response
                        else:
                            return f"❌ Unexpected response format: {type(response)}"

                        # Build formatted story text
                        lines = [
                            f"📚 {data.get('title', 'Untitled Story')}",
                            f"{'=' * 60}",
                            f"Step {data.get('current_step', 0)} of {data.get('total_steps', 0)}",
                            f"{'=' * 60}",
                            "",
                        ]

                        steps = data.get("steps", [])
                        if not steps:
                            lines.append("No story content yet. Start your adventure!")
                        else:
                            for step in steps:
                                lines.append(
                                    f"\n--- Step {step.get('step_index', '?')} ---"
                                )
                                lines.append(step.get("narration", ""))
                                user_action = step.get("user_action")
                                if user_action:
                                    lines.append(f"\n> You: {user_action}")
                                lines.append("")

                        return "\n".join(lines)
                except Exception as e:
                    return f"❌ Failed to load story: {str(e)}"

            refresh_story_btn.click(
                load_full_story, inputs=[session_id_box], outputs=[story_display]
            )

            def download_story(session_id: int):
                """Generate downloadable story file"""
                import tempfile
                import os

                if not session_id or session_id == 0:
                    return None

                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.get(
                            f"{API_BASE}/api/session/{int(session_id)}/story-full"
                        )
                        r.raise_for_status()
                        response = r.json()

                        # Handle response format
                        if isinstance(response, dict):
                            data = response
                        else:
                            return None

                        # Build formatted story text for download
                        lines = [
                            f"{'=' * 70}",
                            f"  {data.get('title', 'Untitled Story')}",
                            f"{'=' * 70}",
                            f"Step {data.get('current_step', 0)} of {data.get('total_steps', 0)}",
                            f"{'=' * 70}",
                            "",
                        ]

                        steps = data.get("steps", [])
                        if steps:
                            for step in steps:
                                lines.append(f"\n{'─' * 70}")
                                lines.append(f"Step {step.get('step_index', '?')}")
                                lines.append(f"{'─' * 70}")
                                lines.append(step.get("narration", ""))
                                user_action = step.get("user_action")
                                if user_action:
                                    lines.append(f"\n> You: {user_action}")
                                lines.append("")
                        else:
                            lines.append("No story content yet.")

                        story_text = "\n".join(lines)

                        # Generated filename prevents path traversal through story titles.
                        with tempfile.NamedTemporaryFile(
                            mode="w",
                            prefix="storypitch-",
                            suffix=".txt",
                            encoding="utf-8",
                            delete=False,
                        ) as output:
                            output.write(story_text)
                        return output.name

                except Exception as e:
                    logger.error(f"Download failed: {e}")
                    return None

            download_story_btn.click(
                download_story, inputs=[session_id_box], outputs=[download_file_output]
            )
        with gr.Tab("🧠 Memory & World"):
            gr.Markdown(
                """
                ### 🗺️ What You've Discovered

                **🧠 Smart Memory System:**
                - Click "🔄 Analyze & Refresh Memory" to extract detailed information from your recent story
                - The AI will analyze the last narrations and update all memory elements
                - This happens separately from story generation for optimal performance
                """
            )

            memory_status = gr.Markdown(value="", visible=True)
            refresh_memory_btn = gr.Button(
                "🔄 Analyze & Refresh Memory", variant="primary", size="lg"
            )

            with gr.Tabs():
                with gr.Tab("👥 NPCs"):
                    npcs_display = gr.Textbox(
                        label="Characters You've Met",
                        lines=20,
                        max_lines=40,
                        interactive=False,
                        placeholder="NPCs you encounter will be remembered here...",
                        show_label=False,
                    )

                with gr.Tab("🗺️ Locations"):
                    locations_display = gr.Textbox(
                        label="Places You've Visited",
                        lines=20,
                        max_lines=40,
                        interactive=False,
                        placeholder="Locations you discover will be tracked here...",
                        show_label=False,
                    )

                with gr.Tab("🎒 Inventory"):
                    inventory_display = gr.Textbox(
                        label="Your Items",
                        lines=20,
                        max_lines=40,
                        interactive=False,
                        placeholder="Items you collect will appear here...",
                        show_label=False,
                    )

                with gr.Tab("💞 Relationships"):
                    relationships_display = gr.Textbox(
                        label="Your Relationships",
                        lines=20,
                        max_lines=40,
                        interactive=False,
                        placeholder="Your relationships with NPCs will be tracked here...",
                        show_label=False,
                    )

                with gr.Tab("📜 Events"):
                    events_display = gr.Textbox(
                        label="Important Events",
                        lines=20,
                        max_lines=40,
                        interactive=False,
                        placeholder="Major story events will be logged here...",
                        show_label=False,
                    )

                with gr.Tab("🔍 Discoveries"):
                    discoveries_display = gr.Textbox(
                        label="Clues & Secrets",
                        lines=20,
                        max_lines=40,
                        interactive=False,
                        placeholder="Clues and discoveries will be saved here...",
                        show_label=False,
                    )

            def load_memory(session_id: int):
                if not session_id or session_id == 0:
                    empty = "⚠️ No active session. Start a story first!"
                    return empty, empty, empty, empty, empty, empty

                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.get(
                            f"{API_BASE}/api/session/{int(session_id)}/memory"
                        )
                        r.raise_for_status()
                        response = r.json()

                        # Handle response format - extract memory data
                        if isinstance(response, dict):
                            memory = response
                        else:
                            error = f"❌ Unexpected response format: {type(response)}"
                            return error, error, error, error, error, error

                        # Format NPCs
                        npcs = memory.get("npcs", {})
                        if npcs:
                            npc_lines = [
                                "👥 CHARACTERS YOU'VE MET:\n" + "=" * 50 + "\n"
                            ]
                            for name, data in npcs.items():
                                npc_lines.append(f"\n🎭 {name}")
                                npc_lines.append(
                                    f"   Personality: {data.get('personality', 'Unknown')}"
                                )
                                npc_lines.append(
                                    f"   First met: Step {data.get('first_met_step', '?')}"
                                )
                                npc_lines.append(
                                    f"   Interactions: {data.get('interactions', 0)}"
                                )
                                if data.get("notes"):
                                    npc_lines.append(f"   Notes: {data['notes']}")
                            npcs_text = "\n".join(npc_lines)
                        else:
                            npcs_text = "No NPCs encountered yet."

                        # Format Locations
                        locations = memory.get("locations", {})
                        if locations:
                            loc_lines = ["🗺️ PLACES YOU'VE VISITED:\n" + "=" * 50 + "\n"]
                            for name, data in locations.items():
                                loc_lines.append(f"\n📍 {name}")
                                loc_lines.append(
                                    f"   Description: {data.get('description', 'Unknown')}"
                                )
                                loc_lines.append(
                                    f"   Visits: {data.get('visited_count', 0)}"
                                )
                                loc_lines.append(
                                    f"   Last visited: Step {data.get('last_visited_step', '?')}"
                                )
                            locations_text = "\n".join(loc_lines)
                        else:
                            locations_text = "No locations discovered yet."

                        # Format Inventory
                        inventory = memory.get("inventory", [])
                        if inventory:
                            inv_lines = ["🎒 YOUR INVENTORY:\n" + "=" * 50 + "\n"]
                            for item in inventory:
                                if isinstance(item, dict):
                                    inv_lines.append(
                                        f"\n• {item.get('item', 'Unknown item')}"
                                    )
                                    if item.get("description"):
                                        inv_lines.append(f"  {item['description']}")
                                    if item.get("acquired_step"):
                                        inv_lines.append(
                                            f"  Acquired: Step {item['acquired_step']}"
                                        )
                                else:
                                    inv_lines.append(f"\n• {item}")
                            inventory_text = "\n".join(inv_lines)
                        else:
                            inventory_text = "Your inventory is empty."

                        # Format Relationships
                        relationships = memory.get("relationships", {})
                        if relationships:
                            rel_lines = ["💞 YOUR RELATIONSHIPS:\n" + "=" * 50 + "\n"]
                            for npc, data in relationships.items():
                                rel_lines.append(f"\n💝 {npc}")
                                rel_lines.append(
                                    f"   Affinity: {data.get('affinity', 0)}/100"
                                )
                                rel_lines.append(
                                    f"   Trust: {data.get('trust', 0)}/100"
                                )
                                if data.get("notes"):
                                    rel_lines.append(f"   Notes: {data['notes']}")
                            relationships_text = "\n".join(rel_lines)
                        else:
                            relationships_text = "No relationships established yet."

                        # Format Events
                        events = memory.get("events", [])
                        if events:
                            event_lines = ["📜 IMPORTANT EVENTS:\n" + "=" * 50 + "\n"]
                            for event in events[-20:]:  # Show last 20 events
                                if isinstance(event, dict):
                                    # Map importance strings to star counts
                                    importance_map = {
                                        "low": 1,
                                        "normal": 2,
                                        "high": 3,
                                        "critical": 4,
                                    }
                                    importance_level = importance_map.get(
                                        event.get("importance", "normal"), 2
                                    )
                                    importance = "⭐" * importance_level
                                    event_lines.append(
                                        f"\n{importance} Step {event.get('step', '?')}"
                                    )
                                    event_lines.append(
                                        f"   {event.get('description', 'Unknown event')}"
                                    )
                                else:
                                    event_lines.append(f"\n• {event}")
                            events_text = "\n".join(event_lines)
                        else:
                            events_text = "No major events recorded yet."

                        # Format Discoveries
                        discoveries = memory.get("discoveries", [])
                        if discoveries:
                            disc_lines = ["🔍 CLUES & DISCOVERIES:\n" + "=" * 50 + "\n"]
                            for disc in discoveries:
                                if isinstance(disc, dict):
                                    disc_lines.append(
                                        f"\n🔎 {disc.get('discovery', 'Unknown discovery')}"
                                    )
                                    disc_lines.append(
                                        f"   Significance: {disc.get('significance', 'normal')}"
                                    )
                                    disc_lines.append(
                                        f"   Found at: Step {disc.get('step', '?')}"
                                    )
                                else:
                                    disc_lines.append(f"\n🔎 {disc}")
                            discoveries_text = "\n".join(disc_lines)
                        else:
                            discoveries_text = "No discoveries made yet."

                        return (
                            npcs_text,
                            locations_text,
                            inventory_text,
                            relationships_text,
                            events_text,
                            discoveries_text,
                        )

                except Exception as e:
                    error = f"❌ Failed to load memory: {str(e)}"
                    return error, error, error, error, error, error

            def refresh_and_analyze_memory(session_id: int, model: str):
                """
                🧠 NEW: Call the memory analysis API endpoint
                This does deep analysis of recent narrations and extracts ALL memory
                """
                if not session_id or session_id == 0:
                    empty = "⚠️ No active session. Start a story first!"
                    return (
                        gr.update(value=empty),
                        gr.update(value=empty),
                        gr.update(value=empty),
                        gr.update(value=empty),
                        gr.update(value=empty),
                        gr.update(value=empty),
                        gr.update(value=empty),
                    )

                try:
                    with create_sync_client(API_KEY) as client:
                        # Call the NEW refresh-memory endpoint
                        status_msg = (
                            "🧠 Analyzing story and extracting memory... Please wait..."
                        )

                        r = client.post(
                            f"{API_BASE}/api/session/{int(session_id)}/refresh-memory",
                            json={"model": (model or "").lower() or None},
                        )

                        # Handle 409 Conflict (already processing)
                        if r.status_code == 409:
                            busy_msg = "⏳ **Session is busy...**\n\nAnother operation is in progress. Please wait for it to complete before refreshing memory."
                            return (
                                gr.update(value=busy_msg),
                                gr.update(value=""),
                                gr.update(value=""),
                                gr.update(value=""),
                                gr.update(value=""),
                                gr.update(value=""),
                                gr.update(value=""),
                            )

                        r.raise_for_status()
                        result = r.json()

                        if not result.get("success"):
                            error_msg = result.get("message", "Memory analysis failed")
                            return (
                                gr.update(value=f"❌ {error_msg}"),
                                gr.update(value=""),
                                gr.update(value=""),
                                gr.update(value=""),
                                gr.update(value=""),
                                gr.update(value=""),
                                gr.update(value=""),
                            )

                        # Get the extracted memory
                        memory = result.get("memory", {})
                        summary = result.get("summary", "")

                        # Format NPCs
                        npcs = memory.get("npcs", [])
                        if npcs:
                            npc_lines = ["👥 CHARACTERS FOUND:\n" + "=" * 50 + "\n"]
                            for npc in npcs:
                                npc_lines.append(f"\n🎭 {npc.get('name', 'Unknown')}")
                                if npc.get("personality"):
                                    npc_lines.append(
                                        f"   Personality: {npc['personality']}"
                                    )
                                if npc.get("description"):
                                    npc_lines.append(
                                        f"   Description: {npc['description']}"
                                    )
                            npcs_text = "\n".join(npc_lines)
                        else:
                            npcs_text = "No NPCs found in recent story."

                        # Format Locations
                        locations = memory.get("locations", [])
                        if locations:
                            loc_lines = ["🗺️ PLACES DISCOVERED:\n" + "=" * 50 + "\n"]
                            for loc in locations:
                                loc_lines.append(f"\n📍 {loc.get('name', 'Unknown')}")
                                if loc.get("description"):
                                    loc_lines.append(f"   {loc['description']}")
                            locations_text = "\n".join(loc_lines)
                        else:
                            locations_text = "No locations found in recent story."

                        # Format Inventory
                        inventory = memory.get("inventory", [])
                        if inventory:
                            inv_lines = ["🎒 ITEMS FOUND:\n" + "=" * 50 + "\n"]
                            for item in inventory:
                                inv_lines.append(f"\n• {item.get('item', 'Unknown')}")
                                if item.get("description"):
                                    inv_lines.append(f"  {item['description']}")
                            inventory_text = "\n".join(inv_lines)
                        else:
                            inventory_text = "No items found in recent story."

                        # Format Relationships
                        relationships = memory.get("relationships", [])
                        if relationships:
                            rel_lines = [
                                "💞 RELATIONSHIPS DETECTED:\n" + "=" * 50 + "\n"
                            ]
                            for rel in relationships:
                                rel_lines.append(f"\n💝 {rel.get('npc', 'Unknown')}")
                                affinity = rel.get("affinity", 0)
                                rel_lines.append(f"   Affinity: {affinity}/100")
                                if rel.get("status"):
                                    rel_lines.append(f"   Status: {rel['status']}")
                            relationships_text = "\n".join(rel_lines)
                        else:
                            relationships_text = (
                                "No relationships detected in recent story."
                            )

                        # Format Events
                        events = memory.get("events", [])
                        if events:
                            event_lines = ["📜 EVENTS RECORDED:\n" + "=" * 50 + "\n"]
                            for event in events:
                                event_lines.append(f"\n• {event}")
                            events_text = "\n".join(event_lines)
                        else:
                            events_text = "No major events found in recent story."

                        # Format Discoveries
                        discoveries = memory.get("discoveries", [])
                        if discoveries:
                            disc_lines = ["🔍 DISCOVERIES MADE:\n" + "=" * 50 + "\n"]
                            for disc in discoveries:
                                disc_lines.append(f"\n🔎 {disc}")
                            discoveries_text = "\n".join(disc_lines)
                        else:
                            discoveries_text = "No discoveries found in recent story."

                        success_msg = f"✅ {result.get('message', 'Memory refreshed!')}\n\n{summary}"

                        return (
                            gr.update(value=success_msg),
                            gr.update(value=npcs_text),
                            gr.update(value=locations_text),
                            gr.update(value=inventory_text),
                            gr.update(value=relationships_text),
                            gr.update(value=events_text),
                            gr.update(value=discoveries_text),
                        )

                except Exception as e:
                    error_msg = str(e)
                    # Check if it's a 409 error in the exception message
                    if "409" in error_msg or "already processing" in error_msg.lower():
                        busy_msg = "⏳ **Session is busy...**\n\nAnother operation is in progress. Please wait for it to complete before refreshing memory."
                        return (
                            gr.update(value=busy_msg),
                            gr.update(value=""),
                            gr.update(value=""),
                            gr.update(value=""),
                            gr.update(value=""),
                            gr.update(value=""),
                            gr.update(value=""),
                        )
                    error = f"❌ Memory analysis failed: {error_msg}"
                    return (
                        gr.update(value=error),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                        gr.update(value=""),
                    )

            refresh_memory_btn.click(
                refresh_and_analyze_memory,
                inputs=[session_id_box, model_selector],
                outputs=[
                    memory_status,
                    npcs_display,
                    locations_display,
                    inventory_display,
                    relationships_display,
                    events_display,
                    discoveries_display,
                ],
            )

        with gr.Tab("🗄️ Database Manager"):
            gr.Markdown(
                """
                # 🗄️ Advanced Database Management

                **Professional database administration with detailed views and granular control**

                - 👥 **Users**: View all users, see their sessions, delete individually
                - 📚 **Sessions**: Browse all story sessions, view details, manage individually
                - 💾 **Snapshots**: Inspect all saves across all sessions, delete specific saves
                - 🗑️ **Bulk Operations**: Clear all data with confirmation
                """
            )

            admin_status = gr.Markdown(value="", visible=True)

            with gr.Tabs():
                # ===== USERS TAB =====
                with gr.Tab("👥 Users"):
                    gr.Markdown("### 👥 User Management")

                    with gr.Row():
                        refresh_users_btn = gr.Button(
                            "🔄 Refresh Users", variant="primary", scale=1
                        )
                        users_count_display = gr.Markdown("**Total Users:** 0")

                    users_table = gr.Textbox(
                        label="All Users",
                        lines=15,
                        max_lines=30,
                        interactive=False,
                        placeholder="Click 'Refresh Users' to load all users from database...",
                    )

                    gr.Markdown("### 🎯 Manage Specific User")
                    with gr.Row():
                        user_id_input = gr.Number(
                            label="User ID", value=None, precision=0, scale=2
                        )
                        delete_user_btn = gr.Button(
                            "🗑️ Delete User", variant="stop", scale=1
                        )

                    user_action_status = gr.Markdown(value="", visible=True)

                # ===== SESSIONS TAB =====
                with gr.Tab("📚 Sessions"):
                    gr.Markdown("### 📚 Session Management")

                    with gr.Row():
                        refresh_sessions_btn = gr.Button(
                            "🔄 Refresh Sessions", variant="primary", scale=1
                        )
                        sessions_count_display = gr.Markdown("**Total Sessions:** 0")

                    with gr.Row():
                        filter_user_id = gr.Number(
                            label="Filter by User ID (optional)",
                            value=None,
                            precision=0,
                            scale=1,
                            info="Leave empty to show all sessions",
                        )
                        sort_sessions = gr.Dropdown(
                            label="Sort By",
                            choices=[
                                "Newest First",
                                "Oldest First",
                                "Most Steps",
                                "By Title",
                            ],
                            value="Newest First",
                            scale=1,
                        )

                    sessions_table = gr.Textbox(
                        label="All Sessions",
                        lines=15,
                        max_lines=30,
                        interactive=False,
                        placeholder="Click 'Refresh Sessions' to load all story sessions...",
                    )

                    gr.Markdown("### 🎯 Manage Specific Session")
                    with gr.Row():
                        session_id_input = gr.Number(
                            label="Session ID", value=None, precision=0, scale=2
                        )
                        view_session_btn = gr.Button(
                            "👁️ View Details", variant="secondary", scale=1
                        )
                        delete_session_btn = gr.Button(
                            "🗑️ Delete Session", variant="stop", scale=1
                        )

                    session_details = gr.Textbox(
                        label="Session Details",
                        lines=10,
                        interactive=False,
                        placeholder="Select a session and click 'View Details' to see full information...",
                    )

                    session_action_status = gr.Markdown(value="", visible=True)

                # ===== SNAPSHOTS TAB =====
                with gr.Tab("💾 Snapshots"):
                    gr.Markdown("### 💾 Snapshot Management")

                    with gr.Row():
                        refresh_snapshots_btn = gr.Button(
                            "🔄 Refresh Snapshots", variant="primary", scale=1
                        )
                        snapshots_count_display = gr.Markdown("**Total Snapshots:** 0")

                    with gr.Row():
                        filter_session_id = gr.Number(
                            label="Filter by Session ID (optional)",
                            value=None,
                            precision=0,
                            scale=1,
                            info="Leave empty to show all snapshots",
                        )
                        sort_snapshots = gr.Dropdown(
                            label="Sort By",
                            choices=[
                                "Newest First",
                                "Oldest First",
                                "By Session",
                                "By Title",
                            ],
                            value="Newest First",
                            scale=1,
                        )

                    snapshots_table = gr.Textbox(
                        label="All Snapshots",
                        lines=15,
                        max_lines=30,
                        interactive=False,
                        placeholder="Click 'Refresh Snapshots' to load all saves...",
                    )

                    gr.Markdown("### 🎯 Manage Specific Snapshot")
                    with gr.Row():
                        snapshot_id_input = gr.Number(
                            label="Snapshot ID", value=None, precision=0, scale=2
                        )
                        view_snapshot_btn = gr.Button(
                            "👁️ View Details", variant="secondary", scale=1
                        )
                        delete_snapshot_btn = gr.Button(
                            "🗑️ Delete Snapshot", variant="stop", scale=1
                        )

                    snapshot_details = gr.Textbox(
                        label="Snapshot Details",
                        lines=10,
                        interactive=False,
                        placeholder="Select a snapshot and click 'View Details' to see full information...",
                    )

                    snapshot_action_status = gr.Markdown(value="", visible=True)

                # ===== DANGER ZONE =====
                with gr.Tab("⚠️ Danger Zone"):
                    gr.Markdown(
                        """
                        # ⚠️ DANGER ZONE

                        **WARNING: These operations are IRREVERSIBLE!**

                        Use these functions with extreme caution. All data will be permanently deleted.
                        """
                    )

                    with gr.Accordion("🗑️ Clear All Data", open=False):
                        gr.Markdown(
                            """
                            ### ⚠️ NUCLEAR OPTION: Clear Entire Database

                            This will delete:
                            - ❌ All users
                            - ❌ All sessions
                            - ❌ All snapshots
                            - ❌ All story steps
                            - ❌ All game progress

                            **This action CANNOT be undone!**
                            """
                        )

                        confirm_text = gr.Textbox(
                            label="Type 'DELETE EVERYTHING' to confirm",
                            placeholder="Type here to confirm...",
                            value="",
                        )

                        clear_all_btn = gr.Button(
                            "💣 CLEAR ALL DATA", variant="stop", size="lg"
                        )
                        clear_all_status = gr.Markdown(value="", visible=True)

            # ===== USERS FUNCTIONS =====
            def refresh_users_list():
                """Load and display all users with detailed information"""
                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.get(f"{API_BASE}/api/admin/users")
                        r.raise_for_status()
                        users = r.json().get("users", [])

                        if not users:
                            return (
                                "📭 No users found in database.",
                                "**Total Users:** 0",
                            )

                        # Format users table
                        lines = [
                            "👥 ALL USERS",
                            "=" * 80,
                            f"{'ID':<6} {'Username':<20} {'Created At':<25}",
                            "-" * 80,
                        ]

                        for u in users:
                            lines.append(
                                f"{u['id']:<6} {u['username']:<20} {u['created_at'][:19]:<25}"
                            )

                        lines.append("-" * 80)
                        lines.append(f"Total: {len(users)} users")

                        return "\n".join(lines), f"**Total Users:** {len(users)}"

                except Exception as e:
                    logger.error(f"Failed to load users: {e}")
                    return f"❌ Error loading users: {str(e)}", "**Total Users:** Error"

            def delete_user_by_id(user_id):
                """Delete a specific user by ID"""
                if not user_id or user_id <= 0:
                    return "⚠️ Please enter a valid User ID", None, None

                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.delete(f"{API_BASE}/api/admin/user/{int(user_id)}")
                        r.raise_for_status()

                        # Refresh the users list
                        users_text, count = refresh_users_list()

                        return (
                            f"✅ User #{int(user_id)} deleted successfully!",
                            users_text,
                            count,
                        )

                except Exception as e:
                    logger.error(f"Failed to delete user: {e}")
                    return f"❌ Error deleting user: {str(e)}", None, None

            # ===== SESSIONS FUNCTIONS =====
            def refresh_sessions_list(filter_user=None, sort_by="Newest First"):
                """Load and display all sessions with filtering and sorting"""
                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.get(f"{API_BASE}/api/admin/sessions")
                        r.raise_for_status()
                        sessions = r.json().get("sessions", [])

                        # Apply filter
                        if filter_user and filter_user > 0:
                            sessions = [
                                s for s in sessions if s["user_id"] == int(filter_user)
                            ]

                        if not sessions:
                            return "📭 No sessions found.", "**Total Sessions:** 0"

                        # Apply sorting
                        if sort_by == "Newest First":
                            sessions.sort(key=lambda x: x["created_at"], reverse=True)
                        elif sort_by == "Oldest First":
                            sessions.sort(key=lambda x: x["created_at"])
                        elif sort_by == "Most Steps":
                            sessions.sort(key=lambda x: x["current_step"], reverse=True)
                        elif sort_by == "By Title":
                            sessions.sort(key=lambda x: x["title"])

                        # Format sessions table
                        lines = [
                            "📚 ALL SESSIONS",
                            "=" * 100,
                            f"{'ID':<6} {'User':<6} {'Title':<30} {'Step':<6} {'Created At':<25}",
                            "-" * 100,
                        ]

                        for s in sessions:
                            title = (
                                s["title"][:28] + ".."
                                if len(s["title"]) > 30
                                else s["title"]
                            )
                            lines.append(
                                f"{s['id']:<6} {s['user_id']:<6} {title:<30} {s['current_step']:<6} {s['created_at'][:19]:<25}"
                            )

                        lines.append("-" * 100)
                        lines.append(f"Total: {len(sessions)} sessions")

                        return "\n".join(lines), f"**Total Sessions:** {len(sessions)}"

                except Exception as e:
                    logger.error(f"Failed to load sessions: {e}")
                    return (
                        f"❌ Error loading sessions: {str(e)}",
                        "**Total Sessions:** Error",
                    )

            def view_session_details(session_id):
                """View detailed information about a specific session"""
                if not session_id or session_id <= 0:
                    return "⚠️ Please enter a valid Session ID"

                try:
                    with create_sync_client(API_KEY) as client:
                        # Get session info
                        r = client.get(f"{API_BASE}/api/admin/sessions")
                        r.raise_for_status()
                        sessions = r.json().get("sessions", [])

                        session = next(
                            (s for s in sessions if s["id"] == int(session_id)), None
                        )
                        if not session:
                            return f"❌ Session #{int(session_id)} not found"

                        # Get full story
                        r2 = client.get(
                            f"{API_BASE}/api/session/{int(session_id)}/story-full"
                        )
                        r2.raise_for_status()
                        story = r2.json()

                        # Format details
                        lines = [
                            f"📚 SESSION #{session['id']} DETAILS",
                            "=" * 70,
                            f"Title: {session['title']}",
                            f"User ID: {session['user_id']}",
                            f"Current Step: {session['current_step']}",
                            f"Total Steps: {story.get('total_steps', 0)}",
                            f"Created: {session['created_at'][:19]}",
                            "",
                            "📖 Story Progress:",
                            "-" * 70,
                        ]

                        steps = story.get("steps", [])
                        if steps:
                            # Show first and last few steps
                            show_count = min(3, len(steps))
                            for step in steps[:show_count]:
                                lines.append(f"\nStep {step['step_index']}:")
                                narration = (
                                    step["narration"][:100] + "..."
                                    if len(step["narration"]) > 100
                                    else step["narration"]
                                )
                                lines.append(f"  {narration}")

                            if len(steps) > 6:
                                lines.append(f"\n... ({len(steps) - 6} more steps) ...")

                            if len(steps) > show_count:
                                for step in steps[-show_count:]:
                                    lines.append(f"\nStep {step['step_index']}:")
                                    narration = (
                                        step["narration"][:100] + "..."
                                        if len(step["narration"]) > 100
                                        else step["narration"]
                                    )
                                    lines.append(f"  {narration}")
                        else:
                            lines.append("No steps recorded yet.")

                        return "\n".join(lines)

                except Exception as e:
                    logger.error(f"Failed to view session details: {e}")
                    return f"❌ Error loading session details: {str(e)}"

            def delete_session_by_id(session_id):
                """Delete a specific session by ID"""
                if not session_id or session_id <= 0:
                    return "⚠️ Please enter a valid Session ID", "", None, None

                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.delete(
                            f"{API_BASE}/api/admin/session/{int(session_id)}"
                        )
                        r.raise_for_status()

                        # Refresh the sessions list
                        sessions_text, count = refresh_sessions_list()

                        return (
                            f"✅ Session #{int(session_id)} deleted successfully!",
                            "",
                            sessions_text,
                            count,
                        )

                except Exception as e:
                    logger.error(f"Failed to delete session: {e}")
                    return f"❌ Error deleting session: {str(e)}", "", None, None

            # ===== SNAPSHOTS FUNCTIONS =====
            def refresh_snapshots_list(filter_session=None, sort_by="Newest First"):
                """Load and display all snapshots with filtering and sorting"""
                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.get(f"{API_BASE}/api/admin/snapshots")
                        r.raise_for_status()
                        snapshots = r.json().get("snapshots", [])

                        # Apply filter
                        if filter_session and filter_session > 0:
                            snapshots = [
                                s
                                for s in snapshots
                                if s["session_id"] == int(filter_session)
                            ]

                        if not snapshots:
                            return "📭 No snapshots found.", "**Total Snapshots:** 0"

                        # Apply sorting
                        if sort_by == "Newest First":
                            snapshots.sort(key=lambda x: x["created_at"], reverse=True)
                        elif sort_by == "Oldest First":
                            snapshots.sort(key=lambda x: x["created_at"])
                        elif sort_by == "By Session":
                            snapshots.sort(key=lambda x: x["session_id"])
                        elif sort_by == "By Title":
                            snapshots.sort(key=lambda x: x["title"])

                        # Format snapshots table
                        lines = [
                            "💾 ALL SNAPSHOTS",
                            "=" * 90,
                            f"{'ID':<6} {'Session':<8} {'Title':<30} {'Created At':<25}",
                            "-" * 90,
                        ]

                        for s in snapshots:
                            title = (
                                s["title"][:28] + ".."
                                if len(s["title"]) > 30
                                else s["title"]
                            )
                            lines.append(
                                f"{s['id']:<6} {s['session_id']:<8} {title:<30} {s['created_at'][:19]:<25}"
                            )

                        lines.append("-" * 90)
                        lines.append(f"Total: {len(snapshots)} snapshots")

                        return "\n".join(
                            lines
                        ), f"**Total Snapshots:** {len(snapshots)}"

                except Exception as e:
                    logger.error(f"Failed to load snapshots: {e}")
                    return (
                        f"❌ Error loading snapshots: {str(e)}",
                        "**Total Snapshots:** Error",
                    )

            def view_snapshot_details(snapshot_id):
                """View detailed information about a specific snapshot"""
                if not snapshot_id or snapshot_id <= 0:
                    return "⚠️ Please enter a valid Snapshot ID"

                try:
                    with create_sync_client(API_KEY) as client:
                        # Get snapshot info
                        r = client.get(f"{API_BASE}/api/snapshot/{int(snapshot_id)}")
                        r.raise_for_status()
                        snapshot = r.json()

                        # Format details
                        lines = [
                            f"💾 SNAPSHOT #{snapshot['id']} DETAILS",
                            "=" * 70,
                            f"Title: {snapshot['title']}",
                            f"Session ID: {snapshot['session_id']}",
                            f"Current Step: {snapshot['current_step']}",
                            f"Created: {snapshot['created_at'][:19]}",
                            "",
                            "📝 Description:",
                            "-" * 70,
                            snapshot.get("description", "No description available"),
                            "",
                            "🌍 World State Preview:",
                            "-" * 70,
                        ]

                        world_state = snapshot.get("world_state", {})
                        if isinstance(world_state, dict):
                            # Show key information from world state
                            memory = world_state.get("memory", {})
                            if memory:
                                npcs = memory.get("npcs", {})
                                locations = memory.get("locations", {})
                                inventory = memory.get("inventory", [])

                                lines.append(f"NPCs: {len(npcs)} characters")
                                lines.append(f"Locations: {len(locations)} places")
                                lines.append(f"Inventory: {len(inventory)} items")
                            else:
                                lines.append("No memory data in this snapshot")
                        else:
                            lines.append("World state data not available")

                        return "\n".join(lines)

                except Exception as e:
                    logger.error(f"Failed to view snapshot details: {e}")
                    return f"❌ Error loading snapshot details: {str(e)}"

            def delete_snapshot_by_id(snapshot_id):
                """Delete a specific snapshot by ID"""
                if not snapshot_id or snapshot_id <= 0:
                    return "⚠️ Please enter a valid Snapshot ID", "", None, None

                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.delete(f"{API_BASE}/api/snapshot/{int(snapshot_id)}")
                        r.raise_for_status()

                        # Refresh the snapshots list
                        snapshots_text, count = refresh_snapshots_list()

                        return (
                            f"✅ Snapshot #{int(snapshot_id)} deleted successfully!",
                            "",
                            snapshots_text,
                            count,
                        )

                except Exception as e:
                    logger.error(f"Failed to delete snapshot: {e}")
                    return f"❌ Error deleting snapshot: {str(e)}", "", None, None

            # ===== DANGER ZONE FUNCTIONS =====
            def clear_all_data(confirmation_text):
                """Clear all data from database - requires confirmation"""
                if confirmation_text != "DELETE EVERYTHING":
                    return "⚠️ Confirmation text incorrect. Type 'DELETE EVERYTHING' exactly to proceed."

                try:
                    with create_sync_client(API_KEY) as client:
                        r = client.post(f"{API_BASE}/api/admin/clear-all")
                        r.raise_for_status()
                        result = r.json()

                        return f"✅ {result.get('message', 'All data cleared successfully!')}\n\n⚠️ Database is now empty."

                except Exception as e:
                    logger.error(f"Failed to clear all data: {e}")
                    return f"❌ Error clearing data: {str(e)}"

            # ===== WIRE UP EVENTS =====

            # Users tab
            refresh_users_btn.click(
                refresh_users_list,
                inputs=[],
                outputs=[users_table, users_count_display],
            )

            delete_user_btn.click(
                delete_user_by_id,
                inputs=[user_id_input],
                outputs=[user_action_status, users_table, users_count_display],
            )

            # Sessions tab
            refresh_sessions_btn.click(
                refresh_sessions_list,
                inputs=[filter_user_id, sort_sessions],
                outputs=[sessions_table, sessions_count_display],
            )

            # Auto-refresh when filter/sort changes
            filter_user_id.change(
                refresh_sessions_list,
                inputs=[filter_user_id, sort_sessions],
                outputs=[sessions_table, sessions_count_display],
            )

            sort_sessions.change(
                refresh_sessions_list,
                inputs=[filter_user_id, sort_sessions],
                outputs=[sessions_table, sessions_count_display],
            )

            view_session_btn.click(
                view_session_details,
                inputs=[session_id_input],
                outputs=[session_details],
            )

            delete_session_btn.click(
                delete_session_by_id,
                inputs=[session_id_input],
                outputs=[
                    session_action_status,
                    session_details,
                    sessions_table,
                    sessions_count_display,
                ],
            )

            # Snapshots tab
            refresh_snapshots_btn.click(
                refresh_snapshots_list,
                inputs=[filter_session_id, sort_snapshots],
                outputs=[snapshots_table, snapshots_count_display],
            )

            # Auto-refresh when filter/sort changes
            filter_session_id.change(
                refresh_snapshots_list,
                inputs=[filter_session_id, sort_snapshots],
                outputs=[snapshots_table, snapshots_count_display],
            )

            sort_snapshots.change(
                refresh_snapshots_list,
                inputs=[filter_session_id, sort_snapshots],
                outputs=[snapshots_table, snapshots_count_display],
            )

            view_snapshot_btn.click(
                view_snapshot_details,
                inputs=[snapshot_id_input],
                outputs=[snapshot_details],
            )

            delete_snapshot_btn.click(
                delete_snapshot_by_id,
                inputs=[snapshot_id_input],
                outputs=[
                    snapshot_action_status,
                    snapshot_details,
                    snapshots_table,
                    snapshots_count_display,
                ],
            )

            # Danger zone
            clear_all_btn.click(
                clear_all_data, inputs=[confirm_text], outputs=[clear_all_status]
            )

    # Tips in accordion at bottom
    with gr.Accordion("💡 Quick Tips & Help", open=False):
        gr.Markdown(
            """
            ### How to Use:

            **🎬 Getting Started:**
            1. Fill in your character details (name, traits, etc.)
            2. Choose a theme (random, from list, or custom)
            3. Click "START MY ADVENTURE!"

            **🎮 Playing:**
            - **Button Mode:** Click one of the suggested choices
            - **Custom Mode:** Write your own action (anything you imagine!)
            - Switch between modes anytime using the radio buttons

            **✨ Pro Tips:**
            - Your traits influence the story and available choices
            - Add custom traits for unique character personalities
            - Clues you discover may unlock special story paths
            - Save your progress regularly to avoid losing your adventure
            - Random themes show you what was generated!

            **💾 Saving:**
            - Use "Save Progress" to create a checkpoint
            - Use "Load Last Save" to restore your last checkpoint
            - Export your full story anytime to save as text
            """
        )

if __name__ == "__main__":
    import os

    demo.launch(
        inbrowser=False,
        server_name="127.0.0.1",
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
        share=False,
    )
