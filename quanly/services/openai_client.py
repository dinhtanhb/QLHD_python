from decouple import config
from openai import OpenAI


def hoi_ai(noi_dung: str) -> str:
    client = OpenAI(api_key=config("OPENAI_API_KEY"))
    response = client.responses.create(
        model="gpt-6-luna",
        input=noi_dung,
    )
    return response.output_text