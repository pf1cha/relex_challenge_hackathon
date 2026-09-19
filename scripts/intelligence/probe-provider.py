import asyncio,json
from dotenv import dotenv_values
from app.intelligence.providers import ModelProvider,ProviderSettings,ProviderFailure
async def main():
    cfg=dotenv_values(".env")
    p=ModelProvider(ProviderSettings(base_url=cfg.get("RELEX_MODEL_BASE_URL") or "",model=cfg.get("RELEX_MODEL_NAME") or "",api_key=cfg.get("RELEX_MODEL_API_KEY") or cfg.get("OPENAI_API_KEY") or "",embedding_base_url=cfg.get("RELEX_EMBEDDING_BASE_URL") or "",embedding_model=cfg.get("RELEX_EMBEDDING_MODEL") or "",embedding_api_key=cfg.get("RELEX_EMBEDDING_API_KEY") or cfg.get("OPENAI_API_KEY") or ""))
    try:
        print(json.dumps(await p.generate("probe","Return JSON {\"synthetic\":true}",{"synthetic":True})))
        v=await p.embed(["Synthetic launch agreement"])
        print(json.dumps({"embedding_dimension":len(v[0]),"events":p.events}))
    except ProviderFailure as exc:print("BLOCKED",str(exc));raise SystemExit(2)
    finally:await p.close()
asyncio.run(main())
