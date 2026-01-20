"""
LLM Provider Routing - Admin-configurable provider selection
"""
from typing import Optional, Any
from enum import Enum

from langchain_core.language_models import BaseChatModel
from langchain_community.chat_models import ChatOllama
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger


class LLMProvider(str, Enum):
    BEDROCK = "bedrock"
    OLLAMA = "ollama"


def get_configured_provider(db: Session) -> str:
    """Get the admin-configured LLM provider from database."""
    from app.db.models import SystemSettings
    
    setting = db.query(SystemSettings).filter(
        SystemSettings.key == "llm_provider"
    ).first()
    
    if setting:
        return setting.value
    return settings.LLM_PROVIDER


def get_ollama_settings(db: Session) -> dict:
    """Get Ollama configuration from database."""
    from app.db.models import SystemSettings
    
    model_setting = db.query(SystemSettings).filter(
        SystemSettings.key == "ollama_model"
    ).first()
    
    endpoint_setting = db.query(SystemSettings).filter(
        SystemSettings.key == "ollama_endpoint"
    ).first()
    
    return {
        "model": model_setting.value if model_setting else settings.OLLAMA_MODEL,
        "base_url": endpoint_setting.value if endpoint_setting else settings.OLLAMA_BASE_URL,
    }


def get_bedrock_settings(db: Session) -> dict:
    """Get Bedrock configuration from database."""
    from app.db.models import SystemSettings
    
    model_setting = db.query(SystemSettings).filter(
        SystemSettings.key == "bedrock_model"
    ).first()
    
    return {
        "model_id": model_setting.value if model_setting else settings.BEDROCK_MODEL_ID,
        "region": settings.AWS_REGION,
    }


def get_llm(db: Optional[Session] = None) -> BaseChatModel:
    """
    Get the configured LLM instance.
    
    Admin can switch between Bedrock and Ollama via dashboard.
    All requests go to the configured provider.
    """
    # Determine provider
    if db:
        provider = get_configured_provider(db)
    else:
        provider = settings.LLM_PROVIDER
    
    logger.info(f"Using LLM provider: {provider}")
    
    if provider == LLMProvider.BEDROCK.value:
        return _get_bedrock_llm(db)
    else:
        return _get_ollama_llm(db)


def _get_ollama_llm(db: Optional[Session] = None) -> BaseChatModel:
    """Get Ollama LLM instance."""
    if db:
        config = get_ollama_settings(db)
    else:
        config = {
            "model": settings.OLLAMA_MODEL,
            "base_url": settings.OLLAMA_BASE_URL,
        }
    
    return ChatOllama(
        model=config["model"],
        base_url=config["base_url"],
        temperature=0.7,
    )


def _get_bedrock_llm(db: Optional[Session] = None) -> BaseChatModel:
    """Get AWS Bedrock LLM instance."""
    try:
        from langchain_aws import ChatBedrock
        import boto3
        
        if db:
            config = get_bedrock_settings(db)
        else:
            config = {
                "model_id": settings.BEDROCK_MODEL_ID,
                "region": settings.AWS_REGION,
            }
        
        # Create Bedrock client
        bedrock_runtime = boto3.client(
            "bedrock-runtime",
            region_name=config["region"],
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        
        return ChatBedrock(
            client=bedrock_runtime,
            model_id=config["model_id"],
            model_kwargs={"temperature": 0.7, "max_tokens": 4096},
        )
    except ImportError:
        logger.warning("langchain-aws not installed, falling back to Ollama")
        return _get_ollama_llm(db)
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock: {e}, falling back to Ollama")
        return _get_ollama_llm(db)
