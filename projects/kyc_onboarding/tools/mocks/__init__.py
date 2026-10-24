"""SQLite-backed mock implementations of the KYC tools. Name → function map used by tools/registry.py."""

from projects.kyc_onboarding.tools.mocks import document_tools, handoff_tools, identity_tools, risk_tools, screening_tools, supervisor_tools

MOCKS = {
    "classify_document": document_tools.classify_document,
    "extract_document": document_tools.extract_document,
    "verify_pan": identity_tools.verify_pan,
    "ckyc_lookup": identity_tools.ckyc_lookup,
    "check_address_proof": identity_tools.check_address_proof,
    "sanctions_screen": screening_tools.sanctions_screen,
    "pep_check": screening_tools.pep_check,
    "fetch_risk_policy": risk_tools.fetch_risk_policy,
    "compute_risk_score": risk_tools.compute_risk_score,
    "request_customer_info": supervisor_tools.request_customer_info,
    "escalate_to_edd": supervisor_tools.escalate_to_edd,
    "create_customer_record": supervisor_tools.create_customer_record,
    "finalize_application": supervisor_tools.finalize_application,
    "transfer_to_doc_extraction": handoff_tools.transfer_to_doc_extraction,
    "transfer_to_identity": handoff_tools.transfer_to_identity,
    "transfer_to_screening": handoff_tools.transfer_to_screening,
    "transfer_to_risk": handoff_tools.transfer_to_risk,
    "route_to_corporate_stub": handoff_tools.route_to_corporate_stub,
}
