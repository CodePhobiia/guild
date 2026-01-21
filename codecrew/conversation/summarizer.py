"""Automatic conversation summarization for CodeCrew.

The SummaryManager handles:
- Automatic summarization when conversations exceed token thresholds
- Storage and retrieval of summaries from the database
- Integration with ContextAssembler for including summaries in context
- Incremental summarization strategies
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

from codecrew.models.base import ModelClient
from codecrew.models.types import Message

from .persistence import DatabaseManager

if TYPE_CHECKING:
    from codecrew.orchestrator.context import ContextSummarizer

logger = logging.getLogger(__name__)


class Summary(BaseModel):
    """A stored conversation summary."""

    id: str
    session_id: str
    summary_type: str  # 'early', 'mid', 'full', 'incremental'
    content: str
    message_range_start: Optional[str] = None
    message_range_end: Optional[str] = None
    token_count: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def from_db_row(cls, row: dict) -> "Summary":
        """Create a Summary from a database row."""
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            summary_type=row["summary_type"],
            content=row["content"],
            message_range_start=row.get("message_range_start"),
            message_range_end=row.get("message_range_end"),
            token_count=row.get("token_count"),
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if row.get("created_at")
                else datetime.utcnow()
            ),
        )


class SummaryManager:
    """Manages automatic conversation summarization.

    Monitors conversation length and triggers summarization when
    thresholds are exceeded, storing summaries for later context assembly.
    """

    def __init__(
        self,
        db: DatabaseManager,
        summarizer_client: Optional[ModelClient] = None,
        token_threshold: int = 50000,
        summary_target_tokens: int = 1000,
    ):
        """Initialize the summary manager.

        Args:
            db: Database manager for persistence
            summarizer_client: Model client for generating summaries
            token_threshold: Token count that triggers summarization
            summary_target_tokens: Target token count for summaries
        """
        from codecrew.orchestrator.context import ContextSummarizer

        self.db = db
        self._summarizer: Optional["ContextSummarizer"] = None
        self.token_threshold = token_threshold
        self.summary_target_tokens = summary_target_tokens

        if summarizer_client:
            self._summarizer = ContextSummarizer(summarizer_client)

    def set_summarizer_client(self, client: ModelClient) -> None:
        """Set or update the summarizer client.

        Args:
            client: Model client for generating summaries
        """
        from codecrew.orchestrator.context import ContextSummarizer

        self._summarizer = ContextSummarizer(client)

    @property
    def is_enabled(self) -> bool:
        """Check if summarization is enabled (has a client)."""
        return self._summarizer is not None

    async def check_and_summarize(
        self,
        session_id: str,
        messages: list[Message],
        token_counter: ModelClient,
    ) -> Optional[Summary]:
        """Check if summarization is needed and generate if so.

        Args:
            session_id: Current session ID
            messages: Current conversation messages
            token_counter: Model client for counting tokens

        Returns:
            Generated Summary if summarization was triggered, else None
        """
        if not self._summarizer:
            logger.debug("Summarization disabled - no summarizer client")
            return None

        # Estimate current token count
        total_tokens = sum(
            token_counter.count_tokens(m.content) + 4  # +4 for role overhead
            for m in messages
        )

        if total_tokens < self.token_threshold:
            logger.debug(f"Token count {total_tokens} below threshold {self.token_threshold}")
            return None

        logger.info(f"Token threshold exceeded ({total_tokens}/{self.token_threshold}), generating summary")

        # Determine what to summarize
        # Strategy: Summarize the older half of messages
        split_point = len(messages) // 2
        messages_to_summarize = messages[:split_point]

        if len(messages_to_summarize) < 4:
            logger.debug("Too few messages to summarize")
            return None

        # Generate summary
        summary_content = await self._summarizer.summarize(
            messages=messages_to_summarize,
            max_summary_tokens=self.summary_target_tokens,
        )

        # Store the summary
        summary = await self.save_summary(
            session_id=session_id,
            summary_type="incremental",
            content=summary_content,
            message_range_start=getattr(messages_to_summarize[0], "id", None),
            message_range_end=getattr(messages_to_summarize[-1], "id", None),
            token_count=token_counter.count_tokens(summary_content),
        )

        return summary

    async def save_summary(
        self,
        session_id: str,
        summary_type: str,
        content: str,
        message_range_start: Optional[str] = None,
        message_range_end: Optional[str] = None,
        token_count: Optional[int] = None,
    ) -> Summary:
        """Save a summary to the database.

        Args:
            session_id: Session ID
            summary_type: Type of summary
            content: Summary content
            message_range_start: First message ID in range
            message_range_end: Last message ID in range
            token_count: Token count

        Returns:
            Created Summary
        """
        summary_id = str(uuid.uuid4())

        row = await self.db.add_summary(
            summary_id=summary_id,
            session_id=session_id,
            summary_type=summary_type,
            content=content,
            message_range_start=message_range_start,
            message_range_end=message_range_end,
            token_count=token_count,
        )

        return Summary.from_db_row(row)

    async def get_summaries(
        self,
        session_id: str,
        summary_type: Optional[str] = None,
    ) -> list[Summary]:
        """Get all summaries for a session.

        Args:
            session_id: Session ID
            summary_type: Optional type filter

        Returns:
            List of summaries
        """
        rows = await self.db.get_session_summaries(session_id, summary_type)
        return [Summary.from_db_row(row) for row in rows]

    async def get_latest_summary(
        self,
        session_id: str,
        summary_type: Optional[str] = None,
    ) -> Optional[Summary]:
        """Get the most recent summary.

        Args:
            session_id: Session ID
            summary_type: Optional type filter

        Returns:
            Latest summary or None
        """
        row = await self.db.get_latest_summary(session_id, summary_type)
        if row:
            return Summary.from_db_row(row)
        return None

    async def summarize_full_conversation(
        self,
        session_id: str,
        messages: list[Message],
    ) -> Optional[Summary]:
        """Generate a full summary of the entire conversation.

        Useful for session archival or export.

        Args:
            session_id: Session ID
            messages: All messages to summarize

        Returns:
            Generated Summary or None if no summarizer
        """
        if not self._summarizer:
            return None

        if len(messages) < 2:
            return None

        summary_content = await self._summarizer.summarize(
            messages=messages,
            max_summary_tokens=self.summary_target_tokens * 2,  # Allow longer for full summary
        )

        return await self.save_summary(
            session_id=session_id,
            summary_type="full",
            content=summary_content,
            message_range_start=getattr(messages[0], "id", None),
            message_range_end=getattr(messages[-1], "id", None),
        )

    async def get_combined_summary_context(
        self,
        session_id: str,
    ) -> Optional[str]:
        """Get combined summary context for including in prompts.

        Combines all incremental summaries into a single context string.

        Args:
            session_id: Session ID

        Returns:
            Combined summary text or None
        """
        summaries = await self.get_summaries(session_id, summary_type="incremental")

        if not summaries:
            return None

        # Combine summaries chronologically
        combined_parts = []
        for i, summary in enumerate(summaries, 1):
            combined_parts.append(f"[Summary {i}]\n{summary.content}")

        return "\n\n".join(combined_parts)

    async def clear_summaries(self, session_id: str) -> int:
        """Delete all summaries for a session.

        Args:
            session_id: Session ID

        Returns:
            Number of deleted summaries
        """
        return await self.db.delete_session_summaries(session_id)


class SummarizationConfig(BaseModel):
    """Configuration for summarization behavior."""

    enabled: bool = True
    token_threshold: int = 50000
    summary_target_tokens: int = 1000
    summarize_on_archive: bool = True
    include_in_context: bool = True
