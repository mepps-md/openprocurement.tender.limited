# -*- coding: utf-8 -*-
import unittest

from openprocurement.tender.belowthreshold.tests.document import (
    TenderDocumentResourceTestMixin,
    TenderDocumentWithDSResourceTestMixin
)

from openprocurement.tender.limited.tests.base import (
    BaseTenderContentWebTest,
    test_tender_data,
    test_tender_negotiation_data,
    test_tender_negotiation_quick_data
)

from openprocurement.tender.limited.tests.base import skipNegotiation


class TenderDocumentResourceTest(BaseTenderContentWebTest, TenderDocumentResourceTestMixin):
    initial_data = test_tender_data
    docservice = False


@unittest.skipIf(skipNegotiation, "not Implemented")
class TenderNegotiationDocumentResourceTest(TenderDocumentResourceTest):
    initial_data = test_tender_negotiation_data


@unittest.skipIf(skipNegotiation, "not Implemented")
class TenderNegotiationQuickDocumentResourceTest(TenderNegotiationDocumentResourceTest):
    initial_data = test_tender_negotiation_quick_data


class TenderDocumentWithDSResourceTest(TenderDocumentResourceTest, TenderDocumentWithDSResourceTestMixin):
    docservice = True


@unittest.skipIf(skipNegotiation, "not Implemented")
class TenderNegotiationDocumentWithDSResourceTest(TenderDocumentWithDSResourceTest):
    initial_data = test_tender_negotiation_data


@unittest.skipIf(skipNegotiation, "not Implemented")
class TenderNegotiationQuickDocumentWithDSResourceTest(TenderDocumentWithDSResourceTest):
    initial_data = test_tender_negotiation_quick_data


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TenderDocumentResourceTest))
    suite.addTest(unittest.makeSuite(TenderDocumentWithDSResourceTest))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
