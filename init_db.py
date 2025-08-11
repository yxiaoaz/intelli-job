import os
import logging

from dotenv import load_dotenv
from pymilvus import (
    MilvusClient,
    DataType,
    Function,
    FunctionType,
    AnnSearchRequest,
    RRFRanker,
)


from app.config import get_project_root
from app.models.base import Base
from app.models.user import *
from app.models.job import *
from app.services.storage.engine import engine

# load .env
load_dotenv(os.path.join(get_project_root(), ".env"))

logger = logging.getLogger(__name__)


def init_sql_db():
    Base.metadata.create_all(bind=engine)


def init_milvus(rewrite_if_exists: bool = False):

    client = MilvusClient(uri=os.getenv("ZILLIZ_URI"), token=os.getenv("ZILLIZ_TOKEN"))
    collection_name = os.getenv("ZILLIZ_JOB_ITEM_COLLECTION_NAME")

    # what happens if a collection with the same name is already there?
    # by default, continue appending to this collection
    if client.has_collection(collection_name):
        logger.info("A collection with this name is already created.")
        if rewrite_if_exists:
            logger.info("Deleting the old collection, and recreating a new one...")
            client.drop_collection(collection_name)
        else:
            logger.info(
                "We will be continue using the old collection, creation of new vector db is aborted..."
            )
            return

    # create schema
    # id: UUID of length 36
    # content: job title and description, for hybrid search
    # sparse_vector: BM25 feature based on content
    # embedding: semantic embedding
    schema = MilvusClient.create_schema()
    schema.add_field(
        field_name="id",
        datatype=DataType.VARCHAR,
        is_primary=True,
        max_length=36,
    )

    # configuration for sparse indexing
    # supports CN and EN
    schema.add_field(
        field_name="language",  # Field name
        datatype=DataType.VARCHAR,  # String data type
        max_length=5,  # Maximum length (adjust as needed)
    )
    multi_analyzer_params = {
        # Define language-specific analyzers
        # Each analyzer follows this format: <analyzer_name>: <analyzer_params>
        "analyzers": {
            "english": {"type": "english"},  # English-optimized analyzer
            "chinese": {"type": "chinese"},  # Chinese-optimized analyzer
            "default": {"tokenizer": "icu"},  # Required fallback analyzer
        },
        "by_field": "language",  # Field determining analyzer selection
        "alias": {
            "cn": "chinese",  # Use "cn" as shorthand for Chinese
            "en": "english",  # Use "en" as shorthand for English
        },
    }

    schema.add_field(
        field_name="content",
        datatype=DataType.VARCHAR,
        max_length=60000,
        multi_analyzer_params=multi_analyzer_params,
        enable_analyzer=True,  # Enable text analysis
    )

    schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field(
        field_name="embedding",
        datatype=DataType.FLOAT_VECTOR,
        dim=1024,  # Dimension for qwen3
    )

    # for sparse vector
    bm25_function = Function(
        name="bm25",
        function_type=FunctionType.BM25,
        input_field_names=["content"],
        output_field_names="sparse_vector",
    )

    schema.add_function(bm25_function)

    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name="sparse_vector",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
    )
    index_params.add_index(
        field_name="embedding", index_type="FLAT", metric_type="COSINE"
    )

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )
    logger.info(f"Collection '{collection_name}' created successfully")
