# Phase 4: Conversation & Context Management

## Phase Overview
- **Duration Estimate**: 4 days
- **Dependencies**: Phase 1 (Foundation & Project Setup)
- **Unlocks**: Phase 6 (TUI) - session display, Phase 7 (Commands) - session commands
- **Risk Level**: Low

## Objectives
1. Implement full CRUD operations for sessions and messages in SQLite
2. Build conversation manager that maintains history and state
3. Create session management features (save, resume, list, search, export)
4. Implement message pinning for persistent context

## Prerequisites
- [ ] Phase 1 completed - database schema and migrations working
- [ ] Understanding of async SQLite operations
- [ ] Pydantic models for data structures defined

## Deliverables
| Deliverable | Type | Acceptance Criteria |
|-------------|------|---------------------|
| ConversationManager | Code | Full history management with async methods |
| Session CRUD | Code | Create, read, update, delete sessions |
| Message CRUD | Code | Insert, query, update messages with filters |
| Pin management | Code | Pin/unpin messages, retrieve pinned set |
| Session search | Code | Full-text search across message content |
| Export functionality | Code | Export to Markdown and JSON formats |

## Technical Specifications

### Architecture Decisions
1. **Async-First Database Operations**: Use aiosqlite for non-blocking database access
2. **Conversation Manager as Facade**: Single entry point for all conversation operations
3. **Lazy Loading**: Don't load full message history until needed
4. **Session Auto-Save**: Automatic checkpointing at configurable intervals
5. **Full-Text Search with SQLite FTS5**: Native full-text search for efficiency

### Data Models / Schemas

#### Session Model
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class Session:
    id: str
    name: Optional[str] = None
    project_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create_new(cls, project_path: Optional[str] = None) -> "Session":
        return cls(
            id=generate_session_id(),
            project_path=project_path,
        )
```

#### Enhanced Message Model
```python
@dataclass
class Message:
    id: str
    session_id: str
    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_estimate: Optional[float] = None
    is_pinned: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    tool_calls: List[ToolCall] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
        }
```

### Component Breakdown

#### ConversationManager (`codecrew/conversation/manager.py`)
- **Purpose**: Central facade for all conversation operations
- **Location**: `codecrew/conversation/manager.py`
- **Interfaces**:
  ```python
  class ConversationManager:
      def __init__(self, db: DatabaseManager):
          self.db = db
          self._current_session: Optional[Session] = None
          self._message_cache: List[Message] = []
      
      # Session management
      async def create_session(
          self,
          name: Optional[str] = None,
          project_path: Optional[str] = None,
      ) -> Session: ...
      
      async def load_session(self, session_id: str) -> Session: ...
      
      async def get_current_session(self) -> Optional[Session]: ...
      
      async def list_sessions(
          self,
          limit: int = 20,
          offset: int = 0,
      ) -> List[Session]: ...
      
      async def delete_session(self, session_id: str) -> bool: ...
      
      # Message management
      async def add_message(
          self,
          role: str,
          content: str,
          model: Optional[str] = None,
          tokens_used: Optional[int] = None,
          cost_estimate: Optional[float] = None,
      ) -> Message: ...
      
      async def get_messages(
          self,
          limit: Optional[int] = None,
          since: Optional[datetime] = None,
      ) -> List[Message]: ...
      
      async def get_message(self, message_id: str) -> Optional[Message]: ...
      
      # Pin management
      async def pin_message(self, message_id: str) -> bool: ...
      
      async def unpin_message(self, message_id: str) -> bool: ...
      
      async def get_pinned_messages(self) -> List[Message]: ...
      
      async def get_pinned_ids(self) -> Set[str]: ...
      
      # Search and export
      async def search_messages(
          self,
          query: str,
          session_id: Optional[str] = None,
      ) -> List[Message]: ...
      
      async def export_session(
          self,
          session_id: str,
          format: Literal["md", "json"] = "md",
      ) -> str: ...
  ```

#### Session Repository (`codecrew/conversation/repositories/sessions.py`)
- **Purpose**: Low-level session database operations
- **Location**: `codecrew/conversation/repositories/sessions.py`
- **Implementation Notes**: Raw SQL operations, no business logic

#### Message Repository (`codecrew/conversation/repositories/messages.py`)
- **Purpose**: Low-level message database operations
- **Location**: `codecrew/conversation/repositories/messages.py`
- **Implementation Notes**: Handle tool_calls JSON serialization

#### Session Exporter (`codecrew/conversation/export.py`)
- **Purpose**: Export conversations to various formats
- **Location**: `codecrew/conversation/export.py`
- **Interfaces**:
  ```python
  class SessionExporter:
      async def to_markdown(self, session: Session, messages: List[Message]) -> str: ...
      async def to_json(self, session: Session, messages: List[Message]) -> str: ...
  ```

## Implementation Tasks

### Task Group: Database Layer Enhancement
- [ ] **[TASK-4.1]** Add FTS5 virtual table for message search
  - Files: `codecrew/conversation/migrations.py`
  - Details:
    ```sql
    -- Add to migrations
    CREATE VIRTUAL TABLE messages_fts USING fts5(
        content,
        content=messages,
        content_rowid=rowid
    );
    
    -- Triggers to keep FTS in sync
    CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content) 
        VALUES (new.rowid, new.content);
    END;
    
    CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content) 
        VALUES ('delete', old.rowid, old.content);
    END;
    ```
  - Estimate: 1.5 hours

- [ ] **[TASK-4.2]** Implement SessionRepository
  - Files: `codecrew/conversation/repositories/sessions.py`
  - Details:
    ```python
    class SessionRepository:
        def __init__(self, db: DatabaseManager):
            self.db = db
        
        async def create(self, session: Session) -> Session:
            await self.db.execute(
                """INSERT INTO sessions (id, name, project_path, metadata)
                   VALUES (?, ?, ?, ?)""",
                (session.id, session.name, session.project_path, 
                 json.dumps(session.metadata))
            )
            return session
        
        async def get_by_id(self, session_id: str) -> Optional[Session]:
            row = await self.db.fetch_one(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,)
            )
            return self._row_to_session(row) if row else None
        
        async def list_recent(
            self, 
            limit: int = 20, 
            offset: int = 0
        ) -> List[Session]:
            rows = await self.db.fetch_all(
                """SELECT * FROM sessions 
                   ORDER BY updated_at DESC 
                   LIMIT ? OFFSET ?""",
                (limit, offset)
            )
            return [self._row_to_session(r) for r in rows]
        
        async def update_timestamp(self, session_id: str) -> None:
            await self.db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (datetime.utcnow(), session_id)
            )
        
        async def delete(self, session_id: str) -> bool:
            result = await self.db.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,)
            )
            return result.rowcount > 0
    ```
  - Estimate: 2 hours

- [ ] **[TASK-4.3]** Implement MessageRepository
  - Files: `codecrew/conversation/repositories/messages.py`
  - Details: Handle tool_calls JSON serialization, ordering
  - Estimate: 2.5 hours

### Task Group: Conversation Manager
- [ ] **[TASK-4.4]** Create ConversationManager skeleton
  - Files: `codecrew/conversation/manager.py`
  - Details: Initialize repositories, set up caching
  - Estimate: 1 hour

- [ ] **[TASK-4.5]** Implement session management methods
  - Files: `codecrew/conversation/manager.py`
  - Details: create_session, load_session, list_sessions, delete_session
  - Estimate: 2 hours

- [ ] **[TASK-4.6]** Implement message management methods
  - Files: `codecrew/conversation/manager.py`
  - Details:
    ```python
    async def add_message(
        self,
        role: str,
        content: str,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        cost_estimate: Optional[float] = None,
    ) -> Message:
        if not self._current_session:
            raise ValueError("No active session")
        
        message = Message(
            id=generate_message_id(),
            session_id=self._current_session.id,
            role=role,
            content=content,
            model=model,
            tokens_used=tokens_used,
            cost_estimate=cost_estimate,
        )
        
        await self.message_repo.create(message)
        self._message_cache.append(message)
        
        # Update session timestamp
        await self.session_repo.update_timestamp(self._current_session.id)
        
        return message
    ```
  - Estimate: 2 hours

- [ ] **[TASK-4.7]** Implement pin management
  - Files: `codecrew/conversation/manager.py`
  - Details:
    ```python
    async def pin_message(self, message_id: str) -> bool:
        # Update message
        await self.db.execute(
            "UPDATE messages SET is_pinned = TRUE WHERE id = ?",
            (message_id,)
        )
        
        # Add to pinned_context table
        await self.db.execute(
            """INSERT OR IGNORE INTO pinned_context 
               (id, session_id, message_id) VALUES (?, ?, ?)""",
            (generate_id(), self._current_session.id, message_id)
        )
        
        # Update cache
        for msg in self._message_cache:
            if msg.id == message_id:
                msg.is_pinned = True
                break
        
        return True
    ```
  - Estimate: 1.5 hours

### Task Group: Search and Export
- [ ] **[TASK-4.8]** Implement full-text search
  - Files: `codecrew/conversation/manager.py`
  - Details:
    ```python
    async def search_messages(
        self,
        query: str,
        session_id: Optional[str] = None,
    ) -> List[Message]:
        # Use FTS5 for search
        sql = """
            SELECT m.* FROM messages m
            JOIN messages_fts fts ON m.rowid = fts.rowid
            WHERE messages_fts MATCH ?
        """
        params = [query]
        
        if session_id:
            sql += " AND m.session_id = ?"
            params.append(session_id)
        
        sql += " ORDER BY m.created_at DESC LIMIT 50"
        
        rows = await self.db.fetch_all(sql, tuple(params))
        return [self.message_repo._row_to_message(r) for r in rows]
    ```
  - Estimate: 1.5 hours

- [ ] **[TASK-4.9]** Implement SessionExporter
  - Files: `codecrew/conversation/export.py`
  - Details:
    ```python
    class SessionExporter:
        async def to_markdown(
            self, 
            session: Session, 
            messages: List[Message]
        ) -> str:
            lines = [
                f"# CodeCrew Session: {session.name or session.id}",
                f"",
                f"**Created:** {session.created_at.isoformat()}",
                f"**Project:** {session.project_path or 'N/A'}",
                f"",
                "---",
                "",
            ]
            
            for msg in messages:
                role_display = self._get_role_display(msg)
                lines.append(f"## {role_display}")
                lines.append("")
                lines.append(msg.content)
                lines.append("")
                
                if msg.tool_calls:
                    lines.append("### Tool Calls")
                    for tc in msg.tool_calls:
                        lines.append(f"- `{tc.name}`: {json.dumps(tc.arguments)}")
                    lines.append("")
            
            return "\n".join(lines)
        
        async def to_json(
            self, 
            session: Session, 
            messages: List[Message]
        ) -> str:
            data = {
                "session": {
                    "id": session.id,
                    "name": session.name,
                    "project_path": session.project_path,
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                },
                "messages": [msg.to_dict() for msg in messages],
            }
            return json.dumps(data, indent=2)
    ```
  - Estimate: 2 hours

### Task Group: Auto-Save and Recovery
- [ ] **[TASK-4.10]** Implement auto-save mechanism
  - Files: `codecrew/conversation/manager.py`
  - Details:
    ```python
    class ConversationManager:
        def __init__(self, db: DatabaseManager, auto_save_interval: int = 300):
            self._auto_save_task: Optional[asyncio.Task] = None
            self._auto_save_interval = auto_save_interval
        
        async def start_auto_save(self):
            """Start background auto-save task."""
            self._auto_save_task = asyncio.create_task(self._auto_save_loop())
        
        async def _auto_save_loop(self):
            while True:
                await asyncio.sleep(self._auto_save_interval)
                if self._current_session:
                    await self._checkpoint()
        
        async def _checkpoint(self):
            """Ensure all cached data is persisted."""
            await self.session_repo.update_timestamp(self._current_session.id)
            logger.debug(f"Auto-saved session {self._current_session.id}")
    ```
  - Estimate: 1.5 hours

- [ ] **[TASK-4.11]** Implement session recovery for crashes
  - Files: `codecrew/conversation/manager.py`
  - Details: Detect unclean shutdown, offer to resume
  - Estimate: 1 hour

### Task Group: Testing
- [ ] **[TASK-4.12]** Write unit tests for SessionRepository
  - Files: `tests/test_conversation/test_sessions.py`
  - Details: CRUD operations, listing, timestamps
  - Estimate: 1.5 hours

- [ ] **[TASK-4.13]** Write unit tests for MessageRepository
  - Files: `tests/test_conversation/test_messages.py`
  - Details: CRUD, tool_calls serialization, ordering
  - Estimate: 1.5 hours

- [ ] **[TASK-4.14]** Write unit tests for ConversationManager
  - Files: `tests/test_conversation/test_manager.py`
  - Details: Full workflow tests, pin management, search
  - Estimate: 2 hours

- [ ] **[TASK-4.15]** Write tests for export functionality
  - Files: `tests/test_conversation/test_export.py`
  - Details: Markdown and JSON format validation
  - Estimate: 1 hour

## Testing Requirements

### Unit Tests
- [ ] Session creation generates unique IDs
- [ ] Session listing returns in reverse chronological order
- [ ] Session deletion cascades to messages
- [ ] Message insertion maintains order within session
- [ ] Message with tool_calls serializes/deserializes correctly
- [ ] Pin message updates both message and pinned_context
- [ ] Unpin removes from pinned_context
- [ ] Full-text search finds messages by content
- [ ] Export to Markdown produces valid Markdown
- [ ] Export to JSON produces valid JSON

### Integration Tests
- [ ] Create session → add messages → list sessions shows session
- [ ] Load session → get_messages returns all messages
- [ ] Pin message → get_pinned_ids includes message
- [ ] Search across sessions finds matching messages
- [ ] Delete session removes all associated data

### Manual Verification
- [ ] Create multiple sessions, verify listing
- [ ] Send messages, close app, resume session, verify history
- [ ] Pin message, reload, verify pin persisted
- [ ] Search for known content, verify results
- [ ] Export session, open file, verify formatting

## Phase Completion Checklist
- [ ] All deliverables created and reviewed
- [ ] All tests passing
- [ ] Session CRUD operations working
- [ ] Message persistence verified
- [ ] Pin management working
- [ ] Search returning relevant results
- [ ] Export producing valid output
- [ ] Auto-save functioning
- [ ] Code formatted and linted
- [ ] Type hints complete

## Rollback Plan
If issues with persistence:

1. **In-Memory Fallback**: Keep conversation in memory only, disable persistence
2. **Simplified Schema**: Remove FTS, tool_calls JSON, use simpler structure
3. **File-Based Backup**: Write JSON files as backup while fixing SQLite issues

Recovery:
1. Back up database file before changes
2. Run migrations with version checks
3. Test thoroughly before production use

## Notes & Considerations

### Edge Cases
- Very long messages exceeding SQLite limits
- Concurrent access to same database (multiple terminals)
- Unicode handling in full-text search
- Empty sessions (no messages)
- Session name collisions

### Known Limitations
- No support for attachments/files in v1
- Search limited to exact FTS5 syntax
- No pagination for messages within session
- Single-user only (no sharing)

### Future Improvements
- Implement message pagination for very long sessions
- Add attachment support (images, files)
- Implement session sharing/export to cloud
- Add semantic search using embeddings
- Implement message editing/deletion
- Add session tagging/categorization

### Performance Considerations
- Cache recent messages in memory
- Lazy load older messages
- Index session_id for message queries
- Consider write-ahead logging for SQLite
- Batch inserts for tool results
