
from sqlalchemy import text


def apply_database_hardening(db):

    # --------------------------------------------------------
    # Remove empty duplicate agent channels first.
    # --------------------------------------------------------

    db.execute(text("""
        DELETE FROM agent_channels a
        USING agent_channels b
        WHERE
            a.agent_id = b.agent_id
            AND a.channel_type = b.channel_type
            AND a.id > b.id
            AND (
                a.config IS NULL
                OR a.config::text = '{}'
            )
    """))

    # --------------------------------------------------------
    # One channel type per agent.
    # Protects against concurrent duplicate creation.
    # --------------------------------------------------------

    db.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        uq_agent_channels_agent_type
        ON agent_channels (
            agent_id,
            channel_type
        )
    """))

    duplicate_tools = db.execute(
        text("""
            SELECT
                agent_id,
                tool_name,
                COUNT(*)
            FROM agent_tool_assignments
            GROUP BY
                agent_id,
                tool_name
            HAVING COUNT(*) > 1
        """)
    ).all()

    if duplicate_tools:
        raise RuntimeError(
            "Duplicate agent tool assignments exist: "
            + str(duplicate_tools)
        )

    duplicate_knowledge = db.execute(
        text("""
            SELECT
                agent_id,
                document_id,
                COUNT(*)
            FROM agent_knowledge
            GROUP BY
                agent_id,
                document_id
            HAVING COUNT(*) > 1
        """)
    ).all()

    if duplicate_knowledge:
        raise RuntimeError(
            "Duplicate agent knowledge links exist: "
            + str(duplicate_knowledge)
        )

    db.execute(
        text("""
            CREATE UNIQUE INDEX
            IF NOT EXISTS
            uq_agent_tool_assignment
            ON agent_tool_assignments (
                agent_id,
                tool_name
            )
        """)
    )

    db.execute(
        text("""
            CREATE UNIQUE INDEX
            IF NOT EXISTS
            uq_agent_knowledge
            ON agent_knowledge (
                agent_id,
                document_id
            )
        """)
    )

    # --------------------------------------------------------
    # Useful production indexes.
    # --------------------------------------------------------

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS
        ix_agent_channels_company_enabled
        ON agent_channels (
            company_id,
            enabled
        )
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS
        ix_ai_conversations_company_agent
        ON ai_conversations (
            company_id,
            agent_id
        )
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS
        ix_ai_messages_conversation_created
        ON ai_messages (
            conversation_id,
            created_at
        )
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS
        ix_ai_usage_company_created
        ON ai_usage (
            company_id,
            created_at
        )
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS
        ix_audit_logs_company_created
        ON audit_logs (
            company_id,
            created_at
        )
    """))

    db.commit()


def database_integrity_report(db):

    duplicate_channels = db.execute(
        text("""
            SELECT
                agent_id,
                channel_type,
                COUNT(*) AS total
            FROM agent_channels
            GROUP BY
                agent_id,
                channel_type
            HAVING COUNT(*) > 1
        """)
    ).mappings().all()

    orphan_channels = db.execute(
        text("""
            SELECT COUNT(*) AS total
            FROM agent_channels c
            LEFT JOIN ai_agents a
                ON a.id = c.agent_id
            WHERE a.id IS NULL
        """)
    ).scalar()

    orphan_messages = db.execute(
        text("""
            SELECT COUNT(*) AS total
            FROM ai_messages m
            LEFT JOIN ai_conversations c
                ON c.id = m.conversation_id
            WHERE c.id IS NULL
        """)
    ).scalar()

    orphan_usage = db.execute(
        text("""
            SELECT COUNT(*) AS total
            FROM ai_usage u
            LEFT JOIN companies c
                ON c.id = u.company_id
            WHERE c.id IS NULL
        """)
    ).scalar()

    duplicate_tools = db.execute(
        text("""
            SELECT
                agent_id,
                tool_name,
                COUNT(*) AS total
            FROM agent_tool_assignments
            GROUP BY
                agent_id,
                tool_name
            HAVING COUNT(*) > 1
        """)
    ).mappings().all()

    duplicate_knowledge = db.execute(
        text("""
            SELECT
                agent_id,
                document_id,
                COUNT(*) AS total
            FROM agent_knowledge
            GROUP BY
                agent_id,
                document_id
            HAVING COUNT(*) > 1
        """)
    ).mappings().all()

    return {
        "duplicate_channels":
            [dict(x) for x in duplicate_channels],

        "duplicate_tool_assignments":
            [dict(x) for x in duplicate_tools],

        "duplicate_knowledge_links":
            [dict(x) for x in duplicate_knowledge],

        "orphan_channels":
            int(orphan_channels or 0),

        "orphan_messages":
            int(orphan_messages or 0),

        "orphan_usage":
            int(orphan_usage or 0),
    }
