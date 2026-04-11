import asyncio
import os

from azure.identity import ClientSecretCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI


load_dotenv()


async def main() -> None:
    endpoint = (os.getenv('AZURE_OPENAI_REALTIME_ENDPOINT') or os.getenv('AZURE_OPENAI_ENDPOINT') or '').strip()
    endpoint = endpoint.replace('/openai/v1', '').rstrip('/')
    deployment = os.getenv('AZURE_OPENAI_REALTIME_DEPLOYMENT', '').strip()
    api_version = os.getenv('AZURE_OPENAI_REALTIME_API_VERSION', '2026-02-23').strip()

    credential = ClientSecretCredential(
        tenant_id=os.getenv('AZURE_TENANT_ID', ''),
        client_id=os.getenv('AZURE_CLIENT_ID', ''),
        client_secret=os.getenv('AZURE_CLIENT_SECRET', ''),
    )
    token_provider = get_bearer_token_provider(
        credential,
        os.getenv('AZURE_TOKEN_SCOPE', 'https://cognitiveservices.azure.com/.default')
    )

    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )

    async with client.realtime.connect(model=deployment) as connection:
        print(f'connected:{deployment}')
        await connection.session.update(session={
            'modalities': ['text', 'audio'],
            'voice': 'alloy',
            'instructions': 'Reply briefly.',
        })
        print('session-updated')


if __name__ == '__main__':
    asyncio.run(main())