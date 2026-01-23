from langchain_core.prompts import HumanMessagePromptTemplate

HUMAN_PROMPT_ES = HumanMessagePromptTemplate.from_template(
    """
Pregunta del usuario: {question}
"""
)
