from models import AccessLog


def verify_log_chain():
    logs = AccessLog.query.order_by(AccessLog.id).all()
    expected_prev = logs[0].prev_hash if logs else None
    for log in logs:
        if log.prev_hash != expected_prev or log.row_hash != log.compute_hash():
            return {"valid": False, "broken_at": log.id, "checked": len(logs)}
        expected_prev = log.row_hash
    return {"valid": True, "broken_at": None, "checked": len(logs)}
