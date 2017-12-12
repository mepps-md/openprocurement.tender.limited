from openprocurement.tender.limited.models import ReportingTender


def includeme(config):
    config.add_tender_procurementMethodType(ReportingTender)
    config.scan("openprocurement.tender.limited.views")
