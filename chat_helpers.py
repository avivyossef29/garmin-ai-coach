import asyncio
from datetime import datetime

import streamlit as st
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage

from user_storage import save_conversation_by_id


def run_chat_ui(system_prompt, dev_mode, tools, friendly_error):
    """Render the chat UI and handle the agent event loop."""
    if "user_context" not in st.session_state:
        if dev_mode:
            st.session_state.user_context = "Dev mode: Garmin data not loaded. Ask me to fetch it if needed."
        else:
            with st.spinner("Fetching your Garmin data..."):
                try:
                    context = tools[0].invoke({})
                    st.session_state.user_context = context
                except Exception as e:
                    st.session_state.user_context = f"Could not load Garmin data: {friendly_error(e)}"

    if "agent" not in st.session_state:
        today = datetime.now().strftime("%Y-%m-%d")
        populated_prompt = system_prompt.format(
            today=today,
            user_context=st.session_state.user_context,
        )
        st.session_state.agent = create_agent(
            "openai:gpt-4o-mini",
            tools=tools,
            system_prompt=populated_prompt,
        )

        if len(st.session_state.messages) == 0:
            if dev_mode:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "👋 Hi! I'm your AI Running Coach (DEV MODE). How can I help?",
                })
            else:
                with st.spinner("Analyzing your training data..."):
                    try:
                        intro_response = st.session_state.agent.invoke({
                            "messages": [HumanMessage(content="""Introduce yourself as an AI Running Coach. Briefly summarize what you know about the user:
- Name and current fitness level
- Training goal (if any race planned)
- Recent training highlights
- Key metrics (race predictions, suggested paces)

Keep it concise (8-15 sentences max). 

End with: "Is there anything else I should know about you? (injuries, schedule, preferences) Otherwise, how can I help today?"
""")]
                        })
                        intro_message = intro_response["messages"][-1].content
                        st.session_state.messages.append({"role": "assistant", "content": intro_message})
                    except Exception:
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "👋 Hi! I'm your AI Running Coach. I've connected to your Garmin data. How can I help?",
                        })

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("How can I help with your training today?"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        if "user_id" in st.session_state:
            save_conversation_by_id(st.session_state.user_id, st.session_state.messages)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                chat_history = []
                for msg in st.session_state.messages:
                    if msg["role"] == "user":
                        chat_history.append(HumanMessage(content=msg["content"]))
                    else:
                        chat_history.append(AIMessage(content=msg["content"]))

                async def stream_agent_events():
                    response_placeholder = st.empty()
                    full_response = ""
                    tool_statuses = {}

                    async for event in st.session_state.agent.astream_events(
                        {"messages": chat_history},
                        version="v2",
                    ):
                        kind = event["event"]
                        if kind == "on_chat_model_stream":
                            content = event["data"]["chunk"].content
                            if content:
                                full_response += content
                                response_placeholder.markdown(full_response + "▌")
                        elif kind == "on_tool_start":
                            tool_name = event.get("name", "tool")
                            tool_statuses[tool_name] = st.status(f"🔧 Using {tool_name}...", state="running")
                        elif kind == "on_tool_end":
                            tool_name = event.get("name", "tool")
                            if tool_name in tool_statuses:
                                tool_statuses[tool_name].update(state="complete")

                    response_placeholder.markdown(full_response)
                    return full_response

                output = asyncio.run(stream_agent_events())
                st.session_state.messages.append({"role": "assistant", "content": output})

                if "user_id" in st.session_state:
                    save_conversation_by_id(st.session_state.user_id, st.session_state.messages)
            except Exception as e:
                st.error(f"❌ {friendly_error(e)}")
