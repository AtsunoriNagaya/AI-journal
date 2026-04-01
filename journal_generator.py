import os

from prompt_templates import load_prompt_section


def generate_with_gemini(prompt: str) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise RuntimeError("langchain / langchain-google-genai is not installed") from exc

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.9,
        google_api_key=api_key,
    )
    system_text = load_prompt_section("System Prompt")

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            ("human", "{user_prompt}"),
        ]
    )

    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"user_prompt": prompt})
