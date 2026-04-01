import os


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
    system_text = (
        "あなたは日本語の日記作家です。与えられた条件を厳守し、自然で読みやすい文体で出力してください。"
        "各日は見出しの後に本文を続け、本文はおおむね400字（目安350〜450字）にしてください。"
    )

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", system_text),
            ("human", "{user_prompt}"),
        ]
    )

    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"user_prompt": prompt})
