import asyncio
import json
import os
from datetime import datetime
from groq import Groq
import re

import pygame
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Static, Label
from textual.message import Message

class MessageDisplay(Static):
    def __init__(self, sender: str, content: str):
        super().__init__()
        self.sender = sender
        self.content = content

    def render(self):
        return Panel(
            Text(self.content, style="green"),
            title=self.sender.upper(),
            border_style="bold green",
            expand=True
        )

class ChatLog(Vertical):
    def add_message(self, sender: str, content: str):
        self.mount(MessageDisplay(sender, content))
        self.scroll_end(animate=False)

    class ScrollRequest(Message):
        """A custom message to request scrolling."""


class AdventureBot:
    def __init__(self):
        self.system_message = '''
        You are an AI game master for an open-world text-based adventure game. Don't tell them you are a games master or any other detail that will break immersion.
        Your role is to guide the player through a dynamic, immersive experience where they have complete freedom to explore, investigate, and interact with planet RS-232. There are no predefined choices or restrictions.

        The game is set on a remote mining planet where communication has been lost, and strange events have begun to unfold. The player can describe their actions, make choices, or solve problems freely using natural language, and you will adapt the story in response to their input. Their role and abilities will evolve based on the choices they make.

        **Key Guidelines:**
        1. Allow the player to freely describe any actions, decisions, or explorations they want to pursue. Be open to any input.
        2. Respond dynamically by adjusting the story, environment, or consequences to match their actions. No restrictions or predefined lists of actions should be provided.
        3. Track the player's health, equipment, and progress based on their choices and actions. Add unexpected situations like getting a graze on the finger that needs treating before infection sets in or equipment failures.
        4. Keep the narrative immersive, realistic, and reactive to the player's decisions.
        5. Introduce challenges, puzzles, and twists based on the player’s choices, but ensure they can always use their creativity to overcome them.
        6. Do not guide the player to a fixed path. Let their imagination and curiosity drive the story but sticking with the theme.
        7. The player’s choices should shape the unfolding events, including alien encounters, environmental hazards, or technological issues, and the player’s character can change roles or skills accordingly.
        8. The player will have a few other companions of varying backgrounds like doctor, engineer and soldier. They can offer help or even fatally injured. Other people can appear and even join the team.
        
        If the player has a companion behave as if they are asking what to do, otherwise behave as if your the characters inner monologue.
        
        Start by asking the player to describe their character and background if they have not already done so. From that point, respond flexibly to whatever actions or decisions they make. Use natural language understanding to interpret their intentions and build the story from there.
        Keep responses short enough to not overwhelm the player with text.
        '''
        self.conversation = []
        self.api_key = ""
        self.model = "llama3-8b-8192"
        self.load_config()

    def load_config(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            api_file_path = os.path.join(current_dir, '..', '..', 'keys', 'apifile.json')
            
            with open(api_file_path, 'r') as file:
                data = json.load(file)
                self.api_key = data.get("grok")
                if not self.api_key:
                    raise ValueError("API key not found in apifile.json.")
            self.grok_client = Groq(api_key=self.api_key)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading config: {e}")
            print(f"Attempted to load from: {api_file_path}")

    async def get_ai_response(self, user_message):
        self.conversation.append({"role": "user", "content": user_message})
        
        try:
            # Pass the conversation to the model and stream responses
            response = await asyncio.to_thread(
                self.grok_client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    *self.conversation  # Add the conversation history
                ],
                temperature=1,
                max_tokens=1024,
                top_p=1,
                stream=True,
                stop=None
            )
            
            # Stream the response chunks and accumulate the final response content
            ai_message_content = ""
            for chunk in response:
                ai_message_content += chunk.choices[0].delta.content or ""

            # Append the AI's response to the conversation
            self.conversation.append({"role": "assistant", "content": ai_message_content})
            return ai_message_content
        
        except Exception as e:
            return f"Error: {str(e)}"

class AlienConsoleApp(App):
    CSS = """
    Screen {
        background: #001100;
    }

    #chat-container {
        height: 1fr;
        border: solid green;
        overflow-y: auto;
    }

    #chat-log {
        width: 100%;
        height: auto;
    }

    #chat-input {
        dock: bottom;
    }

    Input {
        background: #001100;
        color: #00ff00;
        border: solid green;
    }

    Label {
        color: #00ff00;
    }

    .folder-list {
        width: 20%;
        height: 100%;
        border: solid green;
    }
    """

    def __init__(self):
        super().__init__()
        self.AdventureBot = AdventureBot()
        pygame.mixer.init()
        self.send_sound = pygame.mixer.Sound("send_sound.wav")
        self.receive_sound = pygame.mixer.Sound("receive_sound.wav")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Horizontal(
                Vertical(
                    Label("ALIEN GAMEMASTER", id="terminal-header"),
                    Container(ChatLog(id="chat-log"), id="chat-container"),
                    Input(id="chat-input", placeholder="Enter message...")
                )
            )
        )
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted):
        user_input = event.value
        chat_log = self.query_one(ChatLog)

        chat_log.add_message("PLAYER", user_input)
        self.send_sound.play()
        event.input.value = ""

        self.save_to_file("PLAYER", user_input)

        try:
            await asyncio.sleep(1)

            ai_response = await self.AdventureBot.get_ai_response(user_input)

            chat_log.add_message("GameMaster", ai_response)
            self.receive_sound.play()

            # Post a custom message to request scrolling
            self.post_message(ChatLog.ScrollRequest())

            self.save_to_file("GameMaster", ai_response)

        except Exception as e:
            chat_log.add_message("ERROR", f"Failed to get AI response: {str(e)}")
            self.post_message(ChatLog.ScrollRequest())

    def on_mount(self):
        self.query_one(ChatLog).add_message("GAMEMASTER", "DESCRIBE YOUR CHARACTER. NAME, OCCUPATION, SKILLS, EQUIPMENT")
        pygame.mixer.Sound("startup_sound.wav").play()

    def on_chat_log_scroll_request(self):
        """Handle the custom scroll request message."""
        chat_log = self.query_one(ChatLog)
        chat_log.scroll_end(animate=False)

    def save_to_file(self, sender: str, content: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("chat_log.txt", "a") as f:
            f.write(f"[{timestamp}] {sender}: {content}\n")

if __name__ == "__main__":
    app = AlienConsoleApp()
    app.run()
