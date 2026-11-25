"""End-to-end chatbot orchestrator tying intent, product lookup, and reply generation."""

from __future__ import annotations

import logging

from src.backend_client import BackendClient, BackendClientError, load_sample_products
from src.config import Settings, settings as default_settings
from src.generative_service import GenerativeReplyService
from src.intent_service import IntentService
from src.product_matcher import match_product
from src.schemas import (
    ChatbotRespondData,
    ChatbotRespondRequest,
    DataSource,
    ProductItem,
    QueryStatus,
    SuggestReplyData,
    SuggestReplyRequest,
)

logger = logging.getLogger(__name__)


class ChatbotOrchestrator:
    """Orchestrates intent classification, read-only catalog lookup, and guarded reply generation."""

    def __init__(
        self,
        intent_service: IntentService,
        backend_client: BackendClient,
        generative_service: GenerativeReplyService,
        app_settings: Settings | None = None,
    ) -> None:
        self.intent_service = intent_service
        self.backend_client = backend_client
        self.generative_service = generative_service
        self.settings = app_settings or default_settings

    def resolve_products(
        self,
        request_products: list[ProductItem] | None,
    ) -> tuple[list[ProductItem], DataSource]:
        """Resolve product catalog from request payload -> Express backend -> sample catalog."""
        if request_products is not None:
            return request_products, "request_payload"

        try:
            backend_products = self.backend_client.fetch_products()
            return backend_products, "backend_api"
        except BackendClientError as exc:
            logger.info("Backend catalog unavailable (%s); checking sample fallback.", exc)

        if self.settings.USE_SAMPLE_PRODUCTS_FALLBACK:
            sample_products = load_sample_products(self.settings.SAMPLE_PRODUCTS_PATH)
            return sample_products, "sample_catalog"

        return [], "none"

    def suggest_reply(
        self,
        request: SuggestReplyRequest,
        *,
        catalog_unavailable: bool = False,
    ) -> SuggestReplyData:
        """Generate a grounded reply for an already-classified intent."""
        effective_auto_reply_stock = (
            request.auto_reply_stock_enabled
            if request.auto_reply_stock_enabled is not None
            else self.settings.AUTO_REPLY_STOCK_ENABLED
        )

        query_status: QueryStatus = "not_applicable"
        matched_product = None

        if request.intent == "cek_stok" and not effective_auto_reply_stock:
            query_status = "not_applicable"
            matched_product = None
        elif request.intent in ("cek_stok", "cek_harga"):
            if catalog_unavailable:
                query_status = "catalog_unavailable"
                matched_product = None
            else:
                if request.products is None:
                    products, resolved_source = self.resolve_products(None)
                    if resolved_source == "none":
                        query_status = "catalog_unavailable"
                        matched_product = None
                        return self.generative_service.generate_reply(
                            message=request.message,
                            intent=request.intent,
                            query_status=query_status,
                            matched_product=None,
                            use_generative=request.use_generative,
                            auto_reply_stock_enabled=effective_auto_reply_stock,
                            simulate_failure=request.simulate_failure,
                        )
                else:
                    products = request.products

                match_result = match_product(
                    message=request.message,
                    products=products,
                    low_stock_threshold=self.settings.LOW_STOCK_THRESHOLD,
                )
                if match_result.query_status == "not_found" and match_result.active_product_count == 0:
                    query_status = "catalog_unavailable"
                    matched_product = None
                else:
                    query_status = match_result.query_status
                    matched_product = match_result.matched_product

        return self.generative_service.generate_reply(
            message=request.message,
            intent=request.intent,
            query_status=query_status,
            matched_product=matched_product,
            use_generative=request.use_generative,
            auto_reply_stock_enabled=effective_auto_reply_stock,
            simulate_failure=request.simulate_failure,
        )

    def respond(self, request: ChatbotRespondRequest) -> ChatbotRespondData:
        """Run full chatbot pipeline: intent prediction -> catalog lookup -> guarded reply."""
        intent_prediction = self.intent_service.predict(request.message)
        detected_intent = intent_prediction["intent"]

        effective_auto_reply_stock = (
            request.auto_reply_stock_enabled
            if request.auto_reply_stock_enabled is not None
            else self.settings.AUTO_REPLY_STOCK_ENABLED
        )

        needs_catalog = detected_intent in ("cek_stok", "cek_harga") and not (
            detected_intent == "cek_stok" and not effective_auto_reply_stock
        )

        if needs_catalog:
            products, data_source = self.resolve_products(request.products)
        else:
            products = request.products if request.products is not None else []
            data_source = "request_payload" if request.products is not None else "none"

        reply_data = self.suggest_reply(
            SuggestReplyRequest(
                message=request.message,
                intent=detected_intent,
                products=products,
                use_generative=request.use_generative,
                auto_reply_stock_enabled=effective_auto_reply_stock,
                simulate_failure=request.simulate_failure,
            ),
            catalog_unavailable=(needs_catalog and data_source == "none"),
        )

        return ChatbotRespondData(
            sender_id=request.sender_id,
            channel=request.channel,
            original_message=intent_prediction["original_message"],
            normalized_message=intent_prediction["normalized_message"],
            intent=detected_intent,
            confidence=intent_prediction["confidence"],
            scores=intent_prediction["scores"],
            reply=reply_data.reply,
            source=reply_data.source,
            fallback_used=reply_data.fallback_used,
            fallback_reason=reply_data.fallback_reason,
            query_status=reply_data.query_status,
            matched_product=reply_data.matched_product,
            auto_reply_stock_enabled=reply_data.auto_reply_stock_enabled,
            disclaimer_included=reply_data.disclaimer_included,
            data_source=data_source,
        )
