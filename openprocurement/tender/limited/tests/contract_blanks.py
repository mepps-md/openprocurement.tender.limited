# -*- coding: utf-8 -*-
import unittest
import time
from copy import deepcopy
from iso8601 import parse_date
from datetime import timedelta

from openprocurement.api.utils import get_now
from openprocurement.api.constants import SANDBOX_MODE
from openprocurement.tender.core.constants import STAND_STILL_PENDING_SIGNED
from openprocurement.tender.belowthreshold.tests.base import test_organization


# TenderContractResourceTest

def create_tender_contract(self):
    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.contract_id = response.json['data'][0]['id']

    response = self.app.post_json('/tenders/{}/contracts?acc_token={}'.format(self.tender_id, self.tender_token),
                                  {'data': {'title': 'contract title',
                                            'description': 'contract description',
                                            'awardID': self.award_id}},
                                  status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')

    # at next steps we test to create contract in 'complete' tender status
    # time travel
    tender = self.db.get(self.tender_id)
    for i in tender.get('awards', []):
        if i.get('complaintPeriod', {}):  # reporting procedure does not have complaintPeriod
            i['complaintPeriod']['endDate'] = i['complaintPeriod']['startDate']
    self.db.save(tender)

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')

    response = self.app.get('/tenders/{}'.format(self.tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'complete')

    response = self.app.post_json('/tenders/{}/contracts?acc_token={}'.format(self.tender_id, self.tender_token),
                                  {'data': {'title': 'contract title',
                                            'description': 'contract description',
                                            'awardID': self.award_id}},
                                  status=403)
    self.assertEqual(response.status, '403 Forbidden')

    # at next steps we test to create contract in 'cancelled' tender status
    response = self.app.post_json('/tenders?acc_token={}',
                                  {"data": self.initial_data})
    self.assertEqual(response.status, '201 Created')
    tender_id = response.json['data']['id']
    tender_token = response.json['access']['token']

    response = self.app.post_json('/tenders/{}/cancellations?acc_token={}'.format(
        tender_id, tender_token), {'data': {'reason': 'cancellation reason', 'status': 'active'}})
    self.assertEqual(response.status, '201 Created')

    response = self.app.get('/tenders/{}'.format(tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'cancelled')

    response = self.app.post_json('/tenders/{}/contracts?acc_token={}'.format(tender_id, tender_token),
                                  {'data': {'title': 'contract title',
                                            'description': 'contract description',
                                            'awardID': self.award_id}},
                                  status=403)
    self.assertEqual(response.status, '403 Forbidden')


def patch_tender_contract(self):
    response = self.app.get('/tenders/{}/contracts'.format(
        self.tender_id))
    self.contract_id = response.json['data'][0]['id']

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"value": {"currency": "USD"}}},
        status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"], "Can\'t update currency for contract value")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"value": {"valueAddedTaxIncluded": True}}},
        status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can\'t update valueAddedTaxIncluded for contract value")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"value": {"amount": 501}}},
        status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Value amount should be less or equal to awarded amount (469.0)")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"value": {"amount": 238}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['value']['amount'], 238)

    item = deepcopy(response.json['data']["items"][0])

    # check contract.items modification (contract.item.unit.value.amount
    # modification should be allowed)
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"items": [{'unit': {'value': {'amount': 12}}}]}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.body, 'null')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"items": [{'unit': {'value': {'amount': 12, 'currency': "USD", 'valueAddedTaxIncluded': False}}}]}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.body, 'null')

    # https://github.com/mepps-md/openprocurement.tender.limited/commit/eb06a90e3fd7a0c98a64b75e62a0d29591e1febb
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {'data': {'items': [{
            'description': u"custom item descriptionX",
            'quantity': 5,
            'deliveryLocation': {'latitude': "12.123", 'longitude': "170.123"}
        }]}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.body, 'null')

    # try to add/delete contract item
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {'data': {'items': [{}, item]}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.body, 'null')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    self.assertIn("dateSigned", response.json['data'])

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "cancelled"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't update contract in current (complete) tender status")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "pending"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't update contract in current (complete) tender status")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "active"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't update contract in current (complete) tender status")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"awardID": "894917dc8b1244b6aab9ab0ad8c8f48a"}},
        status=422)
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.content_type, 'application/json')

    # at next steps we test to patch contract in 'cancelled' tender status
    response = self.app.post_json('/tenders?acc_token={}',
                                  {"data": self.initial_data})
    self.assertEqual(response.status, '201 Created')
    tender_id = response.json['data']['id']
    tender_token = response.json['access']['token']

    response = self.app.post_json('/tenders/{}/awards?acc_token={}'.format(
        tender_id, tender_token), {'data': {
            'suppliers': [test_organization], 'status': 'pending',
            'value': {'amount': 500, 'valueAddedTaxIncluded': False}}})
    award_id = response.json['data']['id']
    response = self.app.patch_json('/tenders/{}/awards/{}?acc_token={}'.format(tender_id, award_id, tender_token),
                                   {"data": {'qualified': True, "status": "active"}})

    response = self.app.get('/tenders/{}/contracts'.format(tender_id))
    contract_id = response.json['data'][0]['id']

    response = self.app.post_json('/tenders/{}/cancellations?acc_token={}'.format(tender_id, tender_token),
                                  {'data': {'reason': 'cancellation reason', 'status': 'active'}})
    self.assertEqual(response.status, '201 Created')

    response = self.app.get('/tenders/{}'.format(tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'cancelled')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        tender_id, contract_id, tender_token),
        {"data": {"awardID": "894917dc8b1244b6aab9ab0ad8c8f48a"}},
        status=422)
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.content_type, 'application/json')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        tender_id, contract_id, tender_token), {"data": {"status": "active"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't update contract in current (cancelled) tender status")

    response = self.app.patch_json('/tenders/{}/contracts/some_id?acc_token={}'.format(
        self.tender_id, self.tender_token), {"data": {"status": "active"}}, status=404)
    self.assertEqual(response.status, '404 Not Found')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['status'], 'error')
    self.assertEqual(response.json['errors'], [
        {u'description': u'Not Found', u'location':
            u'url', u'name': u'contract_id'}
    ])

    response = self.app.patch_json('/tenders/some_id/contracts/some_id', {"data": {"status": "active"}}, status=404)
    self.assertEqual(response.status, '404 Not Found')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['status'], 'error')
    self.assertEqual(response.json['errors'], [
        {u'description': u'Not Found', u'location':
            u'url', u'name': u'tender_id'}
    ])

    response = self.app.get('/tenders/{}/contracts/{}'.format(self.tender_id, self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    self.assertEqual(response.json['data']["value"]['amount'], 238)


def tender_contract_signature_date(self):
    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.assertNotIn("dateSigned", response.json['data'][0])
    self.contract_id = response.json['data'][0]['id']

    one_hour_in_furure = (get_now() + timedelta(hours=1)).isoformat()
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"dateSigned": one_hour_in_furure}},
        status=422)
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.json['errors'],
                     [{u'description': [u"Contract signature date can't be in the future"],
                       u'location': u'body',
                       u'name': u'dateSigned'}])

    custom_signature_date = get_now().isoformat()
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"dateSigned": custom_signature_date}})
    self.assertEqual(response.status, '200 OK')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    self.assertEqual(response.json['data']["dateSigned"], custom_signature_date)
    self.assertIn("dateSigned", response.json['data'])


def get_tender_contract(self):
    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.contract_id = response.json['data'][0]['id']

    response = self.app.get('/tenders/{}/contracts/some_id'.format(self.tender_id), status=404)
    self.assertEqual(response.status, '404 Not Found')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['status'], 'error')
    self.assertEqual(response.json['errors'], [
        {u'description': u'Not Found', u'location':
            u'url', u'name': u'contract_id'}
    ])

    response = self.app.get('/tenders/some_id/contracts/some_id', status=404)
    self.assertEqual(response.status, '404 Not Found')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['status'], 'error')
    self.assertEqual(response.json['errors'], [
        {u'description': u'Not Found', u'location':
            u'url', u'name': u'tender_id'}
    ])


def get_tender_contracts(self):
    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')

    response = self.app.get('/tenders/some_id/contracts', status=404)
    self.assertEqual(response.status, '404 Not Found')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['status'], 'error')
    self.assertEqual(response.json['errors'], [
        {u'description': u'Not Found', u'location':
            u'url', u'name': u'tender_id'}
    ])


def patch_tender_contract_pending_signed_status(self):
    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    contract = response.json['data'][0]

    response = self.app.patch_json(
        '/tenders/{}/contracts/{}?acc_token={}'.format(self.tender_id, contract['id'], self.tender_token),
        {"data": {"status": "pending.signed"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "pending.signed")
    last_status_change_date = response.json['data']['date']
    stand_still_end = parse_date(last_status_change_date) + STAND_STILL_PENDING_SIGNED

    response = self.app.patch_json(
        '/tenders/{}/contracts/{}?acc_token={}'.format(self.tender_id, contract['id'], self.tender_token),
        {"data": {"description": "new description"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.body, 'null')

    response = self.app.patch_json(
        '/tenders/{}/contracts/{}?acc_token={}'.format(self.tender_id, contract['id'], self.tender_token),
        {"data": {"status": "pending"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'][0]["description"],
                     'Can\'t return contract to pending status before ({})'.format(stand_still_end.isoformat()))

    # time travel: set last contract status update in 15 mins earlier
    tender = self.db.get(self.tender_id)
    date_in_the_past = parse_date(last_status_change_date) - STAND_STILL_PENDING_SIGNED
    tender['contracts'][-1]["date"] = date_in_the_past.isoformat()
    self.db.save(tender)

    response = self.app.patch_json(
        '/tenders/{}/contracts/{}?acc_token={}'.format(self.tender_id, contract['id'], self.tender_token),
        {"data": {"status": "pending"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "pending")

    response = self.app.patch_json(
        '/tenders/{}/contracts/{}?acc_token={}'.format(self.tender_id, contract['id'], self.tender_token),
        {"data": {"status": "pending.signed"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "pending.signed")

    response = self.app.patch_json(
        '/tenders/{}/contracts/{}?acc_token={}'.format(self.tender_id, contract['id'], self.tender_token),
        {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")


def award_id_change_is_not_allowed(self):
    response = self.app.patch_json('/tenders/{}/awards/{}?acc_token={}'.format(
        self.tender_id, self.award_id, self.tender_token), {"data": {"status": "cancelled"}})
    old_award_id = self.award_id

    # upload new award
    response = self.app.post_json('/tenders/{}/awards?acc_token={}'.format(
        self.tender_id, self.tender_token), {'data': {
            'suppliers': [test_organization],
            'value': {'amount': 500, 'valueAddedTaxIncluded': False}}})
    award = response.json['data']
    response = self.app.patch_json('/tenders/{}/awards/{}?acc_token={}'.format(
        self.tender_id, award['id'], self.tender_token), {"data": {'qualified': True, "status": "active"}})
    response = self.app.get('/tenders/{}/contracts'.format(
        self.tender_id))
    contract = response.json['data'][-1]
    self.assertEqual(contract['awardID'], award['id'])
    self.assertNotEqual(contract['awardID'], old_award_id)

    # try to update awardID value
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, contract['id'], self.tender_token), {"data": {"awardID": old_award_id}})
    response = self.app.get('/tenders/{}/contracts'.format(
        self.tender_id))
    contract = response.json['data'][-1]
    self.assertEqual(contract['awardID'], award['id'])
    self.assertNotEqual(contract['awardID'], old_award_id)

# TenderNegotiationContractResourceTest


def patch_tender_negotiation_contract(self):
    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.contract_id = response.json['data'][0]['id']

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"status": "active"}},
        status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertIn("Can't sign contract before stand-still period end (", response.json['errors'][0]["description"])

    response = self.app.get('/tenders/{}/awards'.format(self.tender_id))
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(len(response.json['data']), 1)
    award = response.json['data'][0]
    start = parse_date(award['complaintPeriod']['startDate'])
    end = parse_date(award['complaintPeriod']['endDate'])
    delta = end - start
    self.assertEqual(delta.days, 0 if SANDBOX_MODE else self.stand_still_period_days)

    # at next steps we test to patch contract in 'complete' tender status
    tender = self.db.get(self.tender_id)
    for i in tender.get('awards', []):
        i['complaintPeriod']['endDate'] = i['complaintPeriod']['startDate']
    self.db.save(tender)

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"value": {"currency": "USD"}}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"], "Can\'t update currency for contract value")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"value": {"valueAddedTaxIncluded": False}}},
        status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can\'t update valueAddedTaxIncluded for contract value")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"value": {"amount": 501}}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Value amount should be less or equal to awarded amount (469.0)")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"value": {"amount": 238}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['value']['amount'], 238)

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    self.assertIn(u"dateSigned", response.json['data'])

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "cancelled"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't update contract in current (complete) tender status")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "pending"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't update contract in current (complete) tender status")

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "active"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't update contract in current (complete) tender status")

    # at next steps we test to patch contract in 'cancelled' tender status
    response = self.app.post_json('/tenders?acc_token={}', {"data": self.initial_data})
    self.assertEqual(response.status, '201 Created')
    tender_id = response.json['data']['id']
    tender_token = response.json['access']['token']

    response = self.app.post_json('/tenders/{}/awards?acc_token={}'.format(tender_id, tender_token),
                                  {'data': {'suppliers': [test_organization], 'status': 'pending'}})
    award_id = response.json['data']['id']
    response = self.app.patch_json('/tenders/{}/awards/{}?acc_token={}'.format(tender_id, award_id, tender_token),
                                   {"data": {'qualified': True, "status": "active"}})

    response = self.app.get('/tenders/{}/contracts'.format(tender_id))
    contract_id = response.json['data'][0]['id']

    response = self.app.post_json('/tenders/{}/cancellations?acc_token={}'.format(tender_id, tender_token),
                                  {'data': {'reason': 'cancellation reason', 'status': 'active'}})
    self.assertEqual(response.status, '201 Created')

    response = self.app.get('/tenders/{}'.format(tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'cancelled')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        tender_id, contract_id, tender_token),
        {"data": {"awardID": "894917dc8b1244b6aab9ab0ad8c8f48a"}},
        status=422)
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.content_type, 'application/json')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        tender_id, contract_id, tender_token), {"data": {"status": "active"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't update contract in current (cancelled) tender status")

    response = self.app.patch_json('/tenders/{}/contracts/some_id?acc_token={}'.format(
        self.tender_id, self.tender_token), {"data": {"status": "active"}}, status=404)
    self.assertEqual(response.status, '404 Not Found')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['status'], 'error')
    self.assertEqual(response.json['errors'], [
        {u'description': u'Not Found', u'location':
            u'url', u'name': u'contract_id'}
    ])

    response = self.app.patch_json('/tenders/some_id/contracts/some_id', {"data": {"status": "active"}}, status=404)
    self.assertEqual(response.status, '404 Not Found')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['status'], 'error')
    self.assertEqual(response.json['errors'], [
        {u'description': u'Not Found', u'location':
            u'url', u'name': u'tender_id'}
    ])

    response = self.app.get('/tenders/{}/contracts/{}'.format(self.tender_id, self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")


def tender_negotiation_contract_signature_date(self):
    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.assertNotIn("dateSigned", response.json['data'][0])
    self.contract_id = response.json['data'][0]['id']

    tender = self.db.get(self.tender_id)
    for i in tender.get('awards', []):
        i['complaintPeriod']['endDate'] = i['complaintPeriod']['startDate']
    self.db.save(tender)

    one_hour_in_furure = (get_now() + timedelta(hours=1)).isoformat()
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"dateSigned": one_hour_in_furure}},
        status=422)
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.json['errors'],
                     [{u'description': [u"Contract signature date can't be in the future"],
                       u'location': u'body',
                       u'name': u'dateSigned'}])

    before_stand_still = i['complaintPeriod']['startDate']
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token),
        {"data": {"dateSigned": before_stand_still}},
        status=422)
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.json['errors'], [{u'description': [u'Contract signature date should be after award complaint period end date ({})'.format(i['complaintPeriod']['endDate'])], u'location': u'body', u'name': u'dateSigned'}])

    custom_signature_date = get_now().isoformat()
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"dateSigned": custom_signature_date}})
    self.assertEqual(response.status, '200 OK')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    self.assertEqual(response.json['data']["dateSigned"], custom_signature_date)
    self.assertIn("dateSigned", response.json['data'])


def items(self):
    response = self.app.get('/tenders/{}?acc_token={}'.format(self.tender_id, self.tender_token))
    tender = response.json['data']

    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.contract1_id = response.json['data'][0]['id']
    self.assertEqual([item['id'] for item in response.json['data'][0]['items']],
                     [item['id'] for item in tender['items']])

# TenderNegotiationLotContractResourceTest


def lot_items(self):
    response = self.app.get('/tenders/{}?acc_token={}'.format(self.tender_id, self.tender_token))
    tender = response.json['data']

    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.contract1_id = response.json['data'][0]['id']
    self.assertEqual([item['id'] for item in response.json['data'][0]['items']],
                     [item['id'] for item in tender['items'] if item['relatedLot'] == self.lot1['id']])


def lot_award_id_change_is_not_allowed(self):
    self.app.patch_json('/tenders/{}/awards/{}?acc_token={}'.format(
        self.tender_id, self.award_id, self.tender_token), {"data": {"status": "cancelled"}})
    old_award_id = self.award_id

    # upload new award
    response = self.app.post_json('/tenders/{}/awards?acc_token={}'.format(self.tender_id, self.tender_token),
                                  {'data': {'suppliers': [test_organization],
                                            'lotID': self.lot1['id']}})
    award = response.json['data']
    self.app.patch_json('/tenders/{}/awards/{}?acc_token={}'.format(
        self.tender_id, award['id'], self.tender_token), {"data": {'qualified': True, "status": "active"}})
    response = self.app.get('/tenders/{}/contracts'.format(
            self.tender_id))
    contract = response.json['data'][-1]
    self.assertEqual(contract['awardID'], award['id'])
    self.assertNotEqual(contract['awardID'], old_award_id)

    # try to update awardID value
    self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, contract['id'], self.tender_token), {"data": {"awardID": old_award_id}})
    response = self.app.get('/tenders/{}/contracts'.format(
            self.tender_id))
    contract = response.json['data'][-1]
    self.assertEqual(contract['awardID'], award['id'])
    self.assertNotEqual(contract['awardID'], old_award_id)


def activate_contract_cancelled_lot(self):
    response = self.app.get('/tenders/{}/lots'.format(self.tender_id))
    lot = response.json['data'][0]

    # Create cancellation on lot
    response = self.app.post_json('/tenders/{}/cancellations?acc_token={}'.format(self.tender_id,
                                                                                  self.tender_token),
                                  {'data': {'reason': 'cancellation reason',
                                            'cancellationOf': 'lot',
                                            'relatedLot': lot['id']}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.json['data']['status'], 'pending')

    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    contract = response.json['data'][0]

    # time travel
    tender = self.db.get(self.tender_id)
    for i in tender.get('awards', []):
        if i.get('complaintPeriod', {}):  # reporting procedure does not have complaintPeriod
            i['complaintPeriod']['endDate'] = i['complaintPeriod']['startDate']
    self.db.save(tender)

    # Try to sign (activate) contract
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(self.tender_id, contract['id'],
                                                                                  self.tender_token),
                                   {'data': {'status': 'active'}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"], "Can\'t update contract while cancellation for corresponding lot exists", )

# TenderNegotiationLot2ContractResourceTest


def sign_second_contract(self):
    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.contract1_id = response.json['data'][0]['id']
    self.contract2_id = response.json['data'][1]['id']

    # at next steps we test to create contract in 'complete' tender status
    # time travel
    tender = self.db.get(self.tender_id)
    for i in tender.get('awards', []):
        if i.get('complaintPeriod', {}):  # reporting procedure does not have complaintPeriod
            i['complaintPeriod']['endDate'] = i['complaintPeriod']['startDate']
    self.db.save(tender)

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract2_id, self.tender_token), {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')

    response = self.app.get('/tenders/{}'.format(self.tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'active')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract1_id, self.tender_token), {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')

    response = self.app.get('/tenders/{}'.format(self.tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'complete')


def create_two_contract(self):
    response = self.app.get('/tenders/{}?acc_token={}'.format(self.tender_id, self.tender_token))
    tender = response.json['data']

    response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
    self.contract1_id = response.json['data'][0]['id']
    self.contract2_id = response.json['data'][1]['id']
    self.assertEqual([item['id'] for item in response.json['data'][0]['items']],
                     [item['id'] for item in tender['items'] if item['relatedLot'] == self.lot1['id']])
    self.assertEqual([item['id'] for item in response.json['data'][1]['items']],
                     [item['id'] for item in tender['items'] if item['relatedLot'] == self.lot2['id']])

    response = self.app.post_json('/tenders/{}/contracts?acc_token={}'.format(self.tender_id, self.tender_token),
                                  {'data': {'title': 'contract title',
                                            'description': 'contract description',
                                            'awardID': self.award1_id}},
                                  status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')

    # at next steps we test to create contract in 'complete' tender status
    # time travel
    tender = self.db.get(self.tender_id)
    for i in tender.get('awards', []):
        if i.get('complaintPeriod', {}):  # reporting procedure does not have complaintPeriod
            i['complaintPeriod']['endDate'] = i['complaintPeriod']['startDate']
    self.db.save(tender)

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract1_id, self.tender_token), {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')

    response = self.app.get('/tenders/{}'.format(self.tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertNotEqual(response.json['data']['status'], 'complete')

    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
        self.tender_id, self.contract2_id, self.tender_token), {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')

    response = self.app.get('/tenders/{}'.format(self.tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'complete')

    response = self.app.post_json('/tenders/{}/contracts?acc_token={}'.format(self.tender_id, self.tender_token),
                                  {'data': {'title': 'contract title',
                                            'description': 'contract description',
                                            'awardID': self.award1_id}},
                                  status=403)
    self.assertEqual(response.status, '403 Forbidden')

    # at next steps we test to create contract in 'cancelled' tender status
    response = self.app.post_json('/tenders?acc_token={}',
                                  {"data": self.initial_data})
    self.assertEqual(response.status, '201 Created')
    tender_id = response.json['data']['id']
    tender_token = response.json['access']['token']

    response = self.app.post_json('/tenders/{}/cancellations?acc_token={}'.format(
        tender_id, tender_token), {'data': {'reason': 'cancellation reason', 'status': 'active'}})
    self.assertEqual(response.status, '201 Created')

    response = self.app.get('/tenders/{}'.format(tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'cancelled')

    response = self.app.post_json('/tenders/{}/contracts?acc_token={}'.format(tender_id, tender_token),
                                  {'data': {'title': 'contract title',
                                            'description': 'contract description',
                                            'awardID': self.award1_id}},
                                  status=403)
    self.assertEqual(response.status, '403 Forbidden')

# TenderNegotiationQuickAccelerationTest


@unittest.skipUnless(SANDBOX_MODE, "not supported accelerator")
def create_tender_contract_negotiation_quick(self):
        response = self.app.get('/tenders/{}/contracts'.format(self.tender_id))
        self.contract_id = response.json['data'][0]['id']

        response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
            self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "active"}}, status=403)
        self.assertEqual(response.status, '403 Forbidden')
        self.assertIn("Can't sign contract before stand-still period end (", response.json['errors'][0]["description"])

        time.sleep(self.time_sleep_in_sec)
        response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(
            self.tender_id, self.contract_id, self.tender_token), {"data": {"status": "active"}})
        self.assertEqual(response.status, '200 OK')


#TenderContractDocumentResourceTest


def create_update_contract_document(self):
    # pending contract status
    response = self.app.post('/tenders/{}/contracts/{}/documents?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), upload_files=[('file', 'name.doc', 'content')])
    self.assertEqual(response.status, '201 Created')
    doc_id = response.json["data"]['id']
    self.assertEqual('name.doc', response.json["data"]["title"])

    # pending.signed contract status
    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(self.tender_id, self.contract_id, self.tender_token),
                                   {"data": {"status": "pending.signed"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'pending.signed')

    response = self.app.post('/tenders/{}/contracts/{}/documents?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), upload_files=[('file', 'name_pending_signed.doc', 'content')],
        status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"], "Can't add document in current contract status")

    response = self.app.put('/tenders/{}/contracts/{}/documents/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, doc_id, self.tender_token), upload_files=[('file', 'name.doc', 'content2')], status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"], "Can't update document in current contract status")


    response = self.app.patch_json('/tenders/{}/contracts/{}?acc_token={}'.format(self.tender_id, self.contract_id, self.tender_token),
                                   {"data": {"status": "active"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'active')

    response = self.app.get('/tenders/{}'.format(self.tender_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'complete')

    response = self.app.post('/tenders/{}/contracts/{}/documents?acc_token={}'.format(
        self.tender_id, self.contract_id, self.tender_token), upload_files=[('file', 'name.doc', 'content')], status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't add document in current (complete) tender status")

    response = self.app.put('/tenders/{}/contracts/{}/documents/{}?acc_token={}'.format(
        self.tender_id, self.contract_id, doc_id, self.tender_token), upload_files=[('file', 'name.doc', 'content2')], status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'][0]["description"],
                     "Can't update document in current (complete) tender status")
