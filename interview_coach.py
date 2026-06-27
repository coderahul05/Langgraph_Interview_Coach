# =============================================================================
# Interview Coach -- A LangGraph Learning Project
# =============================================================================
#
# This project teaches you how LangGraph works by building an interview coaching
# assistant that provides personalized feedback and suggestions.
#
# WHAT THIS DOES:
# A user enters their interview preparation needs (e.g. "I feel unprepared", "I can't answer technical questions",
# "I feel anxious and overwhelmed"). The system runs 3 suggestion engines in
# PARALLEL (technical questions, behavioral questions, relaxation techniques), then a decision node picks the
# best approach and routes to either a QUICK practice (under 5 minutes) or a
# DEEPER session (10-15 minutes) based on severity.
#
# LANGGRAPH CONCEPTS COVERED:
# 1. State Management (Pydantic) -- user feeling flows through the graph
# 2. Nodes -- each function does one job (suggest breathing, mindfulness, etc.)
# 3. Parallel Execution -- 3 suggestion nodes run at the same time
# 4. Fan-in -- waiting for all 3 suggestions before picking the best
# 5. Conditional Edges -- routing to quick vs deep based on severity
# 6. Graph Compilation -- turning the graph definition into a runnable app
#
# GRAPH STRUCTURE:
#
#   START
#     |
#   understand_mood
#     |
#     +---> suggest_breathing --------+
#     |                               |
#     +---> suggest_mindfulness ------+---> pick_best_practice
#     |                               |         |
#     +---> suggest_movement ---------+    (conditional)
#                                        /          \
#                                   quick?         deep?
#                                     |               |
#                               quick_practice   deep_practice
#                                     |               |
#                                    END             END
#
# HOW TO RUN:
#   python mental_wellness_graph.py
#
# DEPENDENCIES (same as requirements.txt):
#   langgraph, langchain-openai, python-dotenv, pydantic
#
# =============================================================================

import sys
import operator
import json
from typing import Annotated

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()


class WellnessState(BaseModel):
    user_feeling: str = ""
    breathing_suggestion: str = ""
    mindfulness_suggestion: str = ""
    movement_suggestion: str = ""
    movie_suggestion: str = ""
    needs_advanced_pack: bool = False
    practice_reason: str = ""
    final_suggestion: str = ""
    messages: Annotated[list, operator.add] = []


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)


def understand_mood(state: WellnessState) -> dict:
    response = llm.invoke(
        f"You are a technical recruiter assistant. "
        f"A user says: '{state.user_feeling}'. "
        f"Acknowledge their ask for the job role"
        f"Then assess and classify the candidate needs as Beginner or Advanced in a word on a new line like: Interview Pack: Beginner"
    )
    return {
        "messages": [f"[understand_mood] {response.content}"]
    }


def suggest_breathing(state: WellnessState) -> dict:
    response = llm.invoke(
        f"You are a technical recruiter specialist. "
        f"The user asks for the following job role: '{state.user_feeling}'. "
        f"Suggest TEN specific technical questions that would help. "
        f"Focus on core technical skills, Questions should assess practical knowledge. "
        f"Keep it under 10 sentences and return only the questions."
    )
    return {
        "Technical_Questions": response.content,
        "messages": [f"[suggest_breathing] Done"]
    }


def suggest_mindfulness(state: WellnessState) -> dict:
    response = llm.invoke(
        f"You are an experienced hiring manager. "
        f"The user asks for the following job role: '{state.user_feeling}'. "
        f"Suggest TEN specific behavioral questions that would help. "
        f"Focus on assessing soft skills, teamwork, and problem-solving. "
        f"Keep it under 10 sentences and return only the questions."
    )
    return {
        "behavioral_questions": response.content,
        "messages": [f"[suggest_mindfulness] Done"]
    }


def suggest_movement(state: WellnessState) -> dict:
    response = llm.invoke(
        f"You are a domain expert. "
        f"The user asks for the following job role: '{state.user_feeling}'. "
        f"Generate 10 highly role-specific interview questions that are tailored to the user's job role. "
        f"The questions should test: Day-to-day responsibilities, industry knowledge, and problem-solving skills. "
        f"Keep it under 10 sentences and return only the questions."
    )
    return {
        "role_specific_questions": response.content,
        "messages": [f"[suggest_movement] Done"]
    }


def pick_best_practice(state: WellnessState) -> dict:
    response = llm.invoke(
        f"You are an interview preparation advisor. The user asks for the following job role: '{state.user_feeling}'.\n\n"
        f"Here are three questions generators from specialists:\n\n"
        f"TECHNICAL:\n{state.breathing_suggestion}\n\n"
        f"BEHAVIORAL:\n{state.mindfulness_suggestion}\n\n"
        f"ROLE-SPECIFIC:\n{state.movement_suggestion}\n\n"
        f"Decide: does this person need a BEGINNER preparation pack (Experience is less than 3 years, Confidence level is low, Candidate has less than 7 days to prepare, Candidate explicitly requests fundamentals revision, ) "
        f"or an ADVANCED preparation pack (Experience is 5+ years, Confidence level is high, Candidate has at least 5 days to prepare, Candidate is targeting senior, lead, architect, manager, or specialist positions, Candidate already understands fundamentals )?\n\n"
        f"Reply STRICTLY in this JSON format (no other text):\n"
        f'{{"needs_advanced_pack": true/false, "reason": "one sentence explanation"}}'
    )
    try:
        result = json.loads(response.content)
        needs_advanced = result["needs_advanced_pack"]
        reason = result["reason"]
    except (json.JSONDecodeError, KeyError):
        needs_advanced = False
        reason = "Could not parse decision, defaulting to beginner pack."

    return {
        "needs_advanced_pack": needs_advanced,
        "practice_reason": reason,
        "messages": [f"[pick_best_practice] advanced_pack={needs_advanced}"]
    }


def quick_practice(state: WellnessState) -> dict:
    response = llm.invoke(
        f"You are an  expert interview coach. The user asks for the following job role: '{state.user_feeling}'.\n\n"
        f"Based on these specialist suggestions, generate a beginner interview practice pack "
        f"that combines the beginner level interview preparation questions focussing on fundamentals:\n\n"
        f"TECHNICAL: {state.breathing_suggestion}\n"
        f"BEHAVIORAL: {state.mindfulness_suggestion}\n"
        f"ROLE-SPECIFIC: {state.movement_suggestion}\n\n"
        f"Format it as a simple numbered list of steps. "
        f"Keep it encouraging, and easy to follow. End with a kind closing line."
    )
    return {
        "final_suggestion": f"BEGINNER INTERVIEW PRACTICE PACK\n{'='*45}\n{response.content}",
        "messages": [f"[quick_practice] Generated quick practice"]
    }


def deep_practice(state: WellnessState) -> dict:
    response = llm.invoke(
        f"You are an  expert interview coach. The user asks for the following job role: '{state.user_feeling}'.\n\n"
        f"Based on these specialist suggestions, generate an advanced interview practice pack "
        f"that thoughtfully combines all three components:\n\n"
        f"TECHNICAL: {state.breathing_suggestion}\n"
        f"BEHAVIORAL: {state.mindfulness_suggestion}\n"
        f"ROLE-SPECIFIC: {state.movement_suggestion}\n\n"
        f"Structure it in 3 phases: Technical, Behavioral, Role-Specific. "
        f"Keep it warm and supportive. End with a kind closing message."
    )
    return {
        "final_suggestion": f"ADVANCED INTERVIEW PRACTICE PACK\n{'='*45}\n{response.content}",
        "messages": [f"[deep_practice] Generated deep session"]
    }


def route_after_decision(state: WellnessState) -> str:
    if state.needs_advanced_pack:
        return "advanced"
    else:
        return "beginner"

def assemble_pack(state):
    # Could do nothing
    return {}

graph = StateGraph(WellnessState)

graph.add_node("understand_mood", understand_mood)
graph.add_node("pick_best_practice", pick_best_practice)
graph.add_node("assemble_pack", assemble_pack)
graph.add_node("suggest_breathing", suggest_breathing)
graph.add_node("suggest_mindfulness", suggest_mindfulness)
graph.add_node("suggest_movement", suggest_movement)
graph.add_node("quick_practice", quick_practice)
graph.add_node("deep_practice", deep_practice)

graph.add_edge(START, "understand_mood")
graph.add_edge("understand_mood", "pick_best_practice")  # This edge is needed to ensure the decision node waits for the suggestions, but the suggestions will run in parallel
graph.add_edge("pick_best_practice", "suggest_breathing")
graph.add_edge("pick_best_practice", "suggest_mindfulness")
graph.add_edge("pick_best_practice", "suggest_movement")
graph.add_edge("suggest_breathing", "assemble_pack")
graph.add_edge("suggest_mindfulness", "assemble_pack")
graph.add_edge("suggest_movement", "assemble_pack")
graph.add_conditional_edges(
    "assemble_pack",
    route_after_decision,
    {
        "beginner": "quick_practice",
        "advanced": "deep_practice",
    }
)
graph.add_edge("quick_practice", END)
graph.add_edge("deep_practice", END)
graph.add_edge
app = graph.compile()


def run_wellness_check(feeling: str):
    print("=" * 55)
    print("  Personalized Interview Practice Suggester")
    print(f"  You said: \"{feeling}\"")
    print("=" * 55)

    result = app.invoke(WellnessState(user_feeling=feeling, messages=[]))

    print("\n" + "=" * 55)
    print("  YOUR PERSONALIZED INTERVIEW PRACTICE")
    print("=" * 55)
    print(f"\n{result['final_suggestion']}")

    print("\n" + "-" * 55)
    print("  MESSAGE LOG")
    print("-" * 55)
    for msg in result["messages"]:
        print(f"  {msg}")

    return result


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  INTERVIEW PRACTICE SUGGESTER")
    print("=" * 55)
    print("\n  Tell me how you're doing and I'll suggest a")
    print("  personalized interview practice just for you.")
    print("  Type 'quit' to exit.\n")

    while True:
        feeling = input("  How are you feeling? > ").strip()

        if feeling.lower() in ("quit", "exit", "q"):
            print("\n  Take care of yourself. Goodbye!\n")
            break

        if not feeling:
            continue

        run_wellness_check(feeling)
        print("\n")
