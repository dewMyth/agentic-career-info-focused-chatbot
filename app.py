from dotenv import load_dotenv 
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr
import resend
from jinja2 import Template

load_dotenv(override=True)


def generate_html_content(message):
    template_str = f"""
    <h1>Hello World {message}</h1>
    """

    template = Template(template_str)
    html_content = template.render(message=message)
    return html_content

def send_email(message):
    resend.api_key = os.getenv("RESEND_API_KEY")
    try:
        r = resend.Emails.send({
            "from": "Chatbot <onboarding@resend.dev>",
            "to": 'akalankadewmith@gmail.com',
            "subject": "Someone wants to ask you a question",
            "html": generate_html_content(message),
        })
        print("Email Sent!")
    except Exception as e:
        print(f"Error: Sending Email: {e}")


def record_user_details(email, name="Name not provided", notes="Notes not provied"):
    send_email(f"Recording interest from {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}


def record_unknown_question(question):
    send_email(f"Recording {question} asked that I couldn't answer")
    return {"recorded": "ok"}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}


tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]

class Me:

    def __init__(self):
        self.openai = OpenAI()
        self.name = "Dewmith Akalanka"
        reader = PdfReader("me/combined.pdf")
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text
        with open("me/summary.txt", "r", encoding="utf-8") as f:
            self.summary = f.read()
    
    def handle_tool_calls(self,tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)


            if tool_name == "record_user_details":
                result = record_user_details(**arguments)
            elif tool_name == "record_unknown_question":
                result = record_unknown_question(**arguments)

            results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
        return results

    def system_prompt(self):
        system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

        system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt

    def chat(self, message, history):
        messages = [{"role":"system", "content":self.system_prompt()}] + history + [{"role":"user", "content":message}]
        done = False

        while not done:

            response = self.openai.chat.completions.create(
                model = "gpt-5-nano",
                messages = messages,
                tools = tools
            )

            finish_reason = response.choices[0].finish_reason

            print(f"Finishing LLM response due to {finish_reason}")

            if finish_reason == "tool_calls":
                message_obj = response.choices[0].message
                tool_calls = message_obj.tool_calls
                print(f"Here is the structure of tool_calls {tool_calls}")

                results = self.handle_tool_calls(tool_calls)

            # ✅ Correct way: add both the model message and the tool results back to the conversation
                messages.append(message_obj)
                messages.extend(results)
            else:
                done = True

        return response.choices[0].message.content



if __name__ == "__main__":
    me = Me()
    # response = me.chat("Please ask Dewmith to contact me on jogingds@gmail.com, I am a recruiter", [])
    # print(response)
    app = gr.ChatInterface(me.chat, type="messages").launch()
    port = int(os.getenv("PORT"))
    app.launch(server_name="0.0.0.0", server_port=port)




