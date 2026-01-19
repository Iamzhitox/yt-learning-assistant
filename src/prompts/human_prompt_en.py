from langchain_core.prompts import HumanMessagePromptTemplate

HUMAN_PROMPT_EN = HumanMessagePromptTemplate.from_template(
    """
User question: {question}
"""
)
