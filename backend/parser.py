"""
PostgreSQL SQL AST Parser module using pglast.
Part of the Migration Safety Checker ().

Extracts semantic operations, targets (tables/columns), statement line numbers,
and AST details without executing any migration SQL.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pglast
from pglast.enums.parsenodes import AlterTableType, ConstrType, ObjectType


@dataclass
class ParsedStatement:
    index: int
    statement_type: str
    table_name: Optional[str]
    column_name: Optional[str]
    line_number: int
    raw_sql: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    success: bool
    statements: List[ParsedStatement] = field(default_factory=list)
    has_lock_timeout: bool = False
    lock_timeout_value: Optional[str] = None
    error: Optional[str] = None
    error_line: Optional[int] = None
    total_statements: int = 0


def _extract_table_name(range_var) -> Optional[str]:
    """Extract relname from a RangeVar node."""
    if range_var is None:
        return None
    return getattr(range_var, 'relname', None)


def _extract_type_name(type_name_node) -> str:
    """Format type name from TypeName AST node."""
    if not type_name_node:
        return ""
    names = []
    if hasattr(type_name_node, 'names') and type_name_node.names:
        for n in type_name_node.names:
            val = getattr(n, 'sval', None) or getattr(n, 'str', None)
            if val and val != 'pg_catalog':
                names.append(val)
    base = ".".join(names) if names else "unknown"

    # Check for modifiers (e.g., varchar(50))
    mods = []
    if hasattr(type_name_node, 'typmods') and type_name_node.typmods:
        for m in type_name_node.typmods:
            if hasattr(m, 'val') and hasattr(m.val, 'ival'):
                mods.append(str(m.val.ival))
    if mods:
        base = f"{base}({', '.join(mods)})"
    return base


def parse_sql_migration(sql_content: str) -> ParseResult:
    """
    Parses full SQL migration content using pglast into structured statements.
    
    Returns a ParseResult with individual statements, line numbers,
    AST details, and file-level lock_timeout detection.
    """
    if not sql_content or not sql_content.strip():
        return ParseResult(success=True, statements=[], total_statements=0)

    try:
        raw_stmts = pglast.parse_sql(sql_content)
    except Exception as exc:
        # Extract line number from parse error if available
        err_msg = str(exc)
        line_num = 1
        if hasattr(exc, 'cursorpos') and exc.cursorpos:
            line_num = sql_content[:exc.cursorpos].count('\n') + 1
        return ParseResult(
            success=False,
            error=f"SQL Parsing Error: {err_msg}",
            error_line=line_num,
            total_statements=0
        )

    parsed_list: List[ParsedStatement] = []
    has_lock_timeout = False
    lock_timeout_val = None

    for idx, raw in enumerate(raw_stmts):
        stmt = raw.stmt
        loc = raw.stmt_location
        length = raw.stmt_len if raw.stmt_len > 0 else (len(sql_content) - loc)
        line_no = sql_content[:loc].count('\n') + 1
        raw_slice = sql_content[loc:loc + length].strip()

        stmt_type = type(stmt).__name__
        details: Dict[str, Any] = {}
        table_name = None
        column_name = None

        # 1. CREATE INDEX
        if stmt_type == 'IndexStmt':
            stmt_kind = "CREATE INDEX"
            table_name = _extract_table_name(stmt.relation)
            idx_name = getattr(stmt, 'idxname', None)
            concurrent = getattr(stmt, 'concurrent', False)
            unique = getattr(stmt, 'unique', False)
            cols = []
            if hasattr(stmt, 'indexParams') and stmt.indexParams:
                for param in stmt.indexParams:
                    col = getattr(param, 'name', None)
                    if col:
                        cols.append(col)
            details = {
                "operation": "CREATE_INDEX",
                "index_name": idx_name,
                "concurrent": concurrent,
                "unique": unique,
                "columns": cols,
            }

        # 2. ALTER TABLE
        elif stmt_type == 'AlterTableStmt':
            stmt_kind = "ALTER TABLE"
            table_name = _extract_table_name(stmt.relation)
            commands = []
            
            if hasattr(stmt, 'cmds') and stmt.cmds:
                for cmd in stmt.cmds:
                    subtype = cmd.subtype
                    subtype_name = subtype.name if hasattr(subtype, 'name') else str(subtype)
                    cmd_info: Dict[str, Any] = {"subtype": subtype_name}

                    # AT_AlterColumnType
                    if subtype == AlterTableType.AT_AlterColumnType:
                        column_name = getattr(cmd, 'name', None)
                        new_type = ""
                        if hasattr(cmd, 'def_') and cmd.def_:
                            new_type = _extract_type_name(getattr(cmd.def_, 'typeName', None))
                        cmd_info.update({
                            "type": "ALTER_COLUMN_TYPE",
                            "column": column_name,
                            "new_type": new_type,
                        })

                    # AT_SetNotNull
                    elif subtype == AlterTableType.AT_SetNotNull:
                        column_name = getattr(cmd, 'name', None)
                        cmd_info.update({
                            "type": "SET_NOT_NULL",
                            "column": column_name,
                        })

                    # AT_AddConstraint
                    elif subtype == AlterTableType.AT_AddConstraint:
                        cdef = getattr(cmd, 'def_', None)
                        con_type = cdef.contype.name if (cdef and hasattr(cdef, 'contype')) else "UNKNOWN"
                        con_name = getattr(cdef, 'conname', None) if cdef else None
                        skip_val = getattr(cdef, 'skip_validation', False) if cdef else False
                        
                        pktable = None
                        fk_cols = []
                        pk_cols = []
                        if cdef and hasattr(cdef, 'pktable') and cdef.pktable:
                            pktable = _extract_table_name(cdef.pktable)
                        if cdef and hasattr(cdef, 'fk_attrs') and cdef.fk_attrs:
                            fk_cols = [getattr(a, 'sval', str(a)) for a in cdef.fk_attrs]
                        if cdef and hasattr(cdef, 'pk_attrs') and cdef.pk_attrs:
                            pk_cols = [getattr(a, 'sval', str(a)) for a in cdef.pk_attrs]

                        cmd_info.update({
                            "type": "ADD_CONSTRAINT",
                            "constraint_type": con_type,
                            "constraint_name": con_name,
                            "skip_validation": skip_val,
                            "pktable": pktable,
                            "fk_columns": fk_cols,
                            "pk_columns": pk_cols,
                        })

                    # AT_AddColumn
                    elif subtype == AlterTableType.AT_AddColumn:
                        cdef = getattr(cmd, 'def_', None)
                        col_name = getattr(cdef, 'colname', None) if cdef else None
                        column_name = col_name
                        col_type = _extract_type_name(getattr(cdef, 'typeName', None)) if cdef else ""
                        has_default = False
                        is_volatile = False
                        default_expr = None
                        is_not_null = False

                        if cdef and hasattr(cdef, 'constraints') and cdef.constraints:
                            for c in cdef.constraints:
                                if hasattr(c, 'contype'):
                                    if c.contype == ConstrType.CONSTR_DEFAULT:
                                        has_default = True
                                        raw_expr = getattr(c, 'raw_expr', None)
                                        expr_type = type(raw_expr).__name__ if raw_expr else ""
                                        default_expr = expr_type
                                        # Check if volatile function like now(), random(), gen_random_uuid()
                                        if expr_type == 'FuncCall':
                                            is_volatile = True
                                    elif c.contype == ConstrType.CONSTR_NOTNULL:
                                        is_not_null = True

                        cmd_info.update({
                            "type": "ADD_COLUMN",
                            "column": col_name,
                            "column_type": col_type,
                            "has_default": has_default,
                            "is_volatile_default": is_volatile,
                            "default_expr": default_expr,
                            "is_not_null": is_not_null,
                        })

                    # AT_DropColumn
                    elif subtype == AlterTableType.AT_DropColumn:
                        col_name = getattr(cmd, 'name', None)
                        column_name = col_name
                        cmd_info.update({
                            "type": "DROP_COLUMN",
                            "column": col_name,
                        })

                    # AT_ValidateConstraint
                    elif subtype == AlterTableType.AT_ValidateConstraint:
                        con_name = getattr(cmd, 'name', None)
                        cmd_info.update({
                            "type": "VALIDATE_CONSTRAINT",
                            "constraint_name": con_name,
                        })

                    commands.append(cmd_info)
            details = {
                "operation": "ALTER_TABLE",
                "commands": commands,
            }

        # 3. UPDATE
        elif stmt_type == 'UpdateStmt':
            stmt_kind = "UPDATE"
            table_name = _extract_table_name(stmt.relation)
            has_where = getattr(stmt, 'whereClause', None) is not None
            target_cols = []
            if hasattr(stmt, 'targetList') and stmt.targetList:
                for target in stmt.targetList:
                    col = getattr(target, 'name', None)
                    if col:
                        target_cols.append(col)
            details = {
                "operation": "UPDATE",
                "has_where": has_where,
                "target_columns": target_cols,
            }

        # 4. DROP (DROP TABLE, DROP INDEX, etc.)
        elif stmt_type == 'DropStmt':
            obj_type = getattr(stmt, 'removeType', None)
            obj_name = obj_type.name if hasattr(obj_type, 'name') else str(obj_type)
            stmt_kind = f"DROP {obj_name.replace('OBJECT_', '')}"
            targets = []
            if hasattr(stmt, 'objects') and stmt.objects:
                for obj in stmt.objects:
                    if isinstance(obj, (list, tuple)) and len(obj) > 0:
                        last_item = obj[-1]
                        name = getattr(last_item, 'sval', str(last_item))
                        targets.append(name)
            if targets:
                table_name = targets[0]
            details = {
                "operation": "DROP",
                "object_type": obj_name,
                "targets": targets,
            }

        # 5. SET (e.g. lock_timeout)
        elif stmt_type == 'VariableSetStmt':
            var_name = getattr(stmt, 'name', '')
            stmt_kind = f"SET {var_name}"
            val_str = ""
            if hasattr(stmt, 'args') and stmt.args:
                arg0 = stmt.args[0]
                if hasattr(arg0, 'val') and hasattr(arg0.val, 'sval'):
                    val_str = arg0.val.sval
                elif hasattr(arg0, 'val') and hasattr(arg0.val, 'ival'):
                    val_str = str(arg0.val.ival)
            if var_name.lower() == 'lock_timeout':
                has_lock_timeout = True
                lock_timeout_val = val_str
            details = {
                "operation": "SET_VARIABLE",
                "variable": var_name,
                "value": val_str,
            }

        # 6. Fallback / Other statements
        else:
            stmt_kind = stmt_type.replace('Stmt', '').upper()
            details = {"operation": stmt_kind}

        parsed_list.append(
            ParsedStatement(
                index=idx + 1,
                statement_type=stmt_kind,
                table_name=table_name,
                column_name=column_name,
                line_number=line_no,
                raw_sql=raw_slice,
                details=details,
            )
        )

    return ParseResult(
        success=True,
        statements=parsed_list,
        has_lock_timeout=has_lock_timeout,
        lock_timeout_value=lock_timeout_val,
        total_statements=len(parsed_list),
    )
