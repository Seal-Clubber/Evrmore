#!/usr/bin/env python3
# Copyright (c) 2017 The Bitcoin Core developers
# Copyright (c) 2017-2020 The Raven Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

"""Testing asset use cases"""

from test_framework.test_framework import EvrmoreTestFramework
from test_framework.util import assert_equal, assert_not_equal, assert_contains_key, assert_is_hash_string, assert_does_not_contain_key, assert_raises_rpc_error, JSONRPCException, Decimal

import string


class TollBurnTest(EvrmoreTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 3
        self.extra_args = [['-assetindex'], ['-assetindex'], ['-assetindex']]

    def activate_tolls(self):
        self.log.info("Generating EVR for node[0] and activating tolls...")
        n0 = self.nodes[0]

        if n0.getblockchaininfo()['bip9_softforks']['toll']['status'] == "active":
            return

        current_height = n0.getblockchaininfo()["blocks"]

        if current_height > 1501:
            self.sync_all()
            return

        self.sync_all()

        if current_height < 1500:
            n0.generate(1500 - current_height)

        self.sync_all()
        assert_equal("active", n0.getblockchaininfo()['bip9_softforks']['toll']['status'])

        # when tolls is active, this call will not throw an error
        toll_info = n0.getcalculatedtoll()
        assert_equal(toll_info['asset_name'], '')
        assert_equal(float(toll_info['toll_fee']), float(0.1))

        # We will undo blocks until tolls isn't active anymore
        hashes_to_add_back = []
        current_height = n0.getblockchaininfo()["blocks"]
        while current_height > 1498:
            blockhash = n0.getblockhash(current_height)
            n0.invalidateblock(blockhash)
            current_height = n0.getblockchaininfo()["blocks"]
            hashes_to_add_back.append(blockhash)

        # Verify that the fork in no longer active, verify that getcalculatedtoll throws an error
        assert_equal("locked_in", n0.getblockchaininfo()['bip9_softforks']['toll']['status'])
        assert_raises_rpc_error(-25, "Tolls not active", n0.getcalculatedtoll, "")

        # Add back the blocks to the chain
        for hash in reversed(hashes_to_add_back):  # ✅ Works without modifying original list
            n0.reconsiderblock(hash)

        assert_equal(n0.getblockchaininfo()["blocks"], 1500)

    def issue_legacy_assets(self):
        self.log.info("Running issue legacy asset test")
        n0, n1 = self.nodes[0], self.nodes[1]

        assets = [("LEGACY_ASSET_FOR_TOLLS", True), ("LEGACY_ASSET_FOR_TOLLS_2", True), ("LEGACY_ASSET_FOR_TOLLS_3", False), ("LEGACY_ASSET_FOR_TOLLS_4", False)]

        # Get EVR for transactions if we don't have much
        if n0.getblockchaininfo()["blocks"] < 200:
            n0.generate(200)
            self.sync_all()

        assert_not_equal("active", n0.getblockchaininfo()['bip9_softforks']['toll']['status'])


        for asset_name, reissuable in assets:
            self.log.info("Calling issue()...")
            address0 = n0.getnewaddress()
            ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
            n0.issue(asset_name=asset_name, qty=1000, to_address=address0, change_address="",
                     units=8, reissuable=reissuable, has_ipfs=True, ipfs_hash=ipfs_hash)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        for asset_name, reissuable in assets:
            assetdata = n0.getassetdata(asset_name)
            assert_equal(assetdata["name"], asset_name)
            assert_equal(assetdata["amount"], 1000)
            assert_equal(assetdata["units"], 8)
            assert_equal(assetdata["reissuable"], reissuable)
            assert_equal(assetdata["has_ipfs"], 1)
            assert_equal(assetdata["toll_amount_mutability"], 0)
            assert_equal(assetdata["toll_amount"], 0)
            assert_equal(assetdata["toll_address_mutability"], 0)
            assert_equal(assetdata["toll_address"], "")
            assert_equal(assetdata["remintable"], 0)

        asset_tags = []
        to_address = n0.getnewaddress()
        change_address = ""
        ipfs_hashes = []
        toll_address = n1.getnewaddress()
        toll_amount = 1

        # Loop 10 times to add TAG1 to TAG10
        for i in range(0, 10):
            asset_tags.append(f"TAG{i+1}")
            ipfs_hashes.append("QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8")

        for asset_name, reissuable in assets:
            if (reissuable) :
                n0.issueunique(asset_name, asset_tags, ipfs_hashes, address0, change_address)

        n0.issue("LEGACY_NO_IPFS_REISS_FALSE", 1000, n0.getnewaddress(), "", 8, False, False, "", "", 0, "", False, False, False)
        n0.issue("LEGACY_NO_IPFS_REISS_FALSE_2", 1000, n0.getnewaddress(), "", 8, False, False, "", "", 0, "", False, False, False)
        n0.issue("LEGACY_NO_IPFS_REISS_FALSE_3", 1000, n0.getnewaddress(), "", 8, False, False, "", "", 0, "", False, False, False)

        n0.issue("LEGACY_W_IPFS_REISS_FALSE", 1000, n0.getnewaddress(), "", 8, False, True, ipfs_hash, "", 0, "", False, False, False)
        n0.issue("LEGACY_W_IPFS_REISS_FALSE_2", 1000, n0.getnewaddress(), "", 8, False, True, ipfs_hash, "", 0, "", False, False, False)
        # Did these issues here for some of the tests just as confirmation that issuing pre-toll-fork assets behaves identically to 
        #     issuing assets post-toll-fork which use none of the new assets metadata fields.

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

    def reissue_legacy_asset_v1_reissuable_true_check_remintable_value(self):
        self.log.info("Running reissue_legacy_asset_v1_reissuable_true_check_remintable_value - requires issue_legacy_asset to be run first")
        n0, n1 = self.nodes[0], self.nodes[1]

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)

        # Valid reissue call, changing the current ipfs hash
        # We need to make sure that the assets remintable flag is updated to correspond with the current reissuable flag
        # which is True for this asset
        n0.reissue("LEGACY_ASSET_FOR_TOLLS", 0, n0.getnewaddress(), "", True, -1, "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU7")

        n0.generate(1)
        self.sync_all()

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 1)

    def reissue_legacy_asset_v1_reissuable_false_check_remintable_value(self):
        self.log.info("Running reissue_legacy_asset_v1_reissuable_false_check_remintable_value - requires issue_legacy_asset to be run first")
        n0, n1 = self.nodes[0], self.nodes[1]

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_3")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS_3")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)

        # Valid reissue call, changing the current ipfs hash
        # We need to make sure that the assets remintable flag stays the same as the current reissuable flag
        # which is False for this asset
        n0.reissue("LEGACY_ASSET_FOR_TOLLS_3", 0, n0.getnewaddress(), "", True, -1, "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU7")

        n0.generate(1)
        self.sync_all()

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_3")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS_3")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU7")
        assert_equal(assetdata["permanent_ipfs_hash"], "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)

    def burn_legacy_asset_v1_reissuable_true_check_remintable(self):
        self.log.info("Running burn_legacy_asset_v1_reissuable_true_check_remintable - requires issue_legacy_asset to be run first")
        n0, n1 = self.nodes[0], self.nodes[1]

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_2")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS_2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)

        BURNMINTADDRESS = "n1BurnMintXXXXXXXXXXXXXXXXXXbVTQiY"
        n0.transfer("LEGACY_ASSET_FOR_TOLLS_2", 500, BURNMINTADDRESS)

        n0.generate(1)
        self.sync_all()

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_2")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS_2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

    def burn_legacy_asset_v1_reissuable_false_check_remintable(self):
        self.log.info("Running burn_legacy_asset_v1_reissuable_false_check_remintable - requires issue_legacy_asset to be run first")
        n0, n1 = self.nodes[0], self.nodes[1]

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_4")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS_4")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)

        BURNMINTADDRESS = "n1BurnMintXXXXXXXXXXXXXXXXXXbVTQiY"
        n0.transfer("LEGACY_ASSET_FOR_TOLLS_4", 500, BURNMINTADDRESS)

        n0.generate(1)
        self.sync_all()

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_4")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS_4")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

    def reissue_toll_amount(self):
        self.log.info("Running reissue toll amount")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("TOLL_AMOUNT", 1000, address0, "",
                 8, False, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, False, False)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_AMOUNT")
        assert_equal(assetdata["name"], "TOLL_AMOUNT")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)


        # call reissue trying to change:
        # Amount to 1000 + 99
        # Reissue to True
        # Units to 4
        # IPFS Hash to the permanent_ipfs_hash - this will always work now once tolls are active
        # Toll Amount to 45
        # Toll Address Mutability to True
        # Toll Address to address 0
        n0.reissue("TOLL_AMOUNT", 99, address0, "", True, 4, permanent_ipfs_hash, "", True, 45, address0, True, True)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # The only things that should have changed are the toll amount to 45 and the ipfs_hash to permanent_ipfs_hash
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_AMOUNT")
        assert_equal(assetdata["name"], "TOLL_AMOUNT")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 45)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)

        # Reissue the asset with a new toll_amount but with "change_toll_amount"=False
        txid = n0.reissue("TOLL_AMOUNT", 0, address0, "", False, -1, "", "", False, 800, "", True, False)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # Nothing should have changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_AMOUNT")
        assert_equal(assetdata["name"], "TOLL_AMOUNT")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 45)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)

        # reissue toll amount from 45 to 100 with with "change_toll_amount"=True - should fail because toll amounts cannot be increased
        try:
            n0.reissue("TOLL_AMOUNT", 0, address0, "", False, -1, "", "", True, 100, "", True, False)
        except JSONRPCException as e:
            if "amount can't be increased" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        # reissue toll amount to 0 with "change_toll_amount"=True
        n0.reissue("TOLL_AMOUNT", 0, address0, "", False, -1, "", "", True, 0, "", True, False)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # The only thing that should have changed is the toll amount to 0
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_AMOUNT")
        assert_equal(assetdata["name"], "TOLL_AMOUNT")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)

        # reissue toll amount from 0 to 100  with "change_toll_amount"=True - should fail because toll amounts cannot be increased
        try:
            n0.reissue("TOLL_AMOUNT", 0, address0, "", False, -1, "", "", True, 100, "", True, False)
        except JSONRPCException as e:
            if "Failed to create reissue asset object. Error: Base: Unable to reissue asset: reissuable is set to false | Amount: Unable to reissue toll amount: amount is already set to zero and can't be changed | Address: Unable to reissue toll address: reissue toll address is set to false" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

    def remint_burn_fee_check(self):
        self.log.info("Running remint burn fee check 0.1 EVR")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("REMINT_BURN_CHECK_1", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, True, True)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REMINT_BURN_CHECK_1")
        assert_equal(assetdata["name"], "REMINT_BURN_CHECK_1")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)
        assert_equal(assetdata["remintable"], 1)


        BURNMINTADDRESS = "n1BurnMintXXXXXXXXXXXXXXXXXXbVTQiY"
        n0.transfer("REMINT_BURN_CHECK_1", 500, BURNMINTADDRESS)

        n0.generate(1)
        self.sync_all()

        assetdata = n0.getassetdata("REMINT_BURN_CHECK_1")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "REMINT_BURN_CHECK_1")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

        # Define the expected output data
        expected_output = {
            'value': Decimal('0.10000000'),
            'n': 0,
            'scriptPubKey': {
                'asm': 'OP_DUP OP_HASH160 da61c47adbad4a81e5f14e1fabb3d167a51ca448 OP_EQUALVERIFY OP_CHECKSIG',
                'hex': '76a914da61c47adbad4a81e5f14e1fabb3d167a51ca44888ac',
                'reqSigs': 1,
                'type': 'pubkeyhash',
                'addresses': ['n1ReissueAssetXXXXXXXXXXXXXXWG9NLd']
            }
        }

        remintaddress = n0.getnewaddress()

        # Remint the asset - This should create a burn tx with 0.1 Evr Burned
        txid = n0.remint("REMINT_BURN_CHECK_1", 250, remintaddress)
        transaction = n0.gettransaction(txid[0])
        decoded = n0.decoderawtransaction(transaction['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['asm'] == expected_output['scriptPubKey']['asm'] and
                        scriptPubKey['hex'] == expected_output['scriptPubKey']['hex'] and
                        scriptPubKey['reqSigs'] == expected_output['scriptPubKey']['reqSigs'] and
                        scriptPubKey['type'] == expected_output['scriptPubKey']['type'] and
                        scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):

                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - Remint amount should have been 0.1"

    def reissue_burn_amount_check_1(self):
        self.log.info("Running reissue burn amount check burning 1 EVR")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("BURN_CHECK_1", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, True)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("BURN_CHECK_1")
        assert_equal(assetdata["name"], "BURN_CHECK_1")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

        # Define the expected output data
        expected_output = {
            'value': Decimal('1.00000000'),
            'n': 0,
            'scriptPubKey': {
                'asm': 'OP_DUP OP_HASH160 da61c47adbad4a81e5f14e1fabb3d167a51ca448 OP_EQUALVERIFY OP_CHECKSIG',
                'hex': '76a914da61c47adbad4a81e5f14e1fabb3d167a51ca44888ac',
                'reqSigs': 1,
                'type': 'pubkeyhash',
                'addresses': ['n1ReissueAssetXXXXXXXXXXXXXXWG9NLd']
            }
        }

        # Reissue the asset but only toll amount - This should create a burn tx with 1 Evr Burned
        txid = n0.reissue("BURN_CHECK_1", 0, address0, "", True, -1, "", "", True, 25, "", True, True)
        transaction = n0.gettransaction(txid[0])
        decoded = n0.decoderawtransaction(transaction['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['asm'] == expected_output['scriptPubKey']['asm'] and
                        scriptPubKey['hex'] == expected_output['scriptPubKey']['hex'] and
                        scriptPubKey['reqSigs'] == expected_output['scriptPubKey']['reqSigs'] and
                        scriptPubKey['type'] == expected_output['scriptPubKey']['type'] and
                        scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):

                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - MetaDataOnly amount should have been 1"

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        # Reissue the asset but only toll address - This should create a burn tx with 1 Evr Burned
        address2 = n0.getnewaddress()
        txid = n0.reissue("BURN_CHECK_1", 0, address0, "", True, -1, "", "", False, 25, address2, True, True)
        transaction = n0.gettransaction(txid[0])
        decoded = n0.decoderawtransaction(transaction['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['asm'] == expected_output['scriptPubKey']['asm'] and
                        scriptPubKey['hex'] == expected_output['scriptPubKey']['hex'] and
                        scriptPubKey['reqSigs'] == expected_output['scriptPubKey']['reqSigs'] and
                        scriptPubKey['type'] == expected_output['scriptPubKey']['type'] and
                        scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):

                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - MetaDataOnly amount should have been 1"

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        # Reissue the asset but setting toll amount mutability to false
        txid = n0.reissue("BURN_CHECK_1", 0, address0, "", True, -1, "", "", False, 25, "", False, True)
        transaction = n0.gettransaction(txid[0])
        decoded = n0.decoderawtransaction(transaction['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['asm'] == expected_output['scriptPubKey']['asm'] and
                        scriptPubKey['hex'] == expected_output['scriptPubKey']['hex'] and
                        scriptPubKey['reqSigs'] == expected_output['scriptPubKey']['reqSigs'] and
                        scriptPubKey['type'] == expected_output['scriptPubKey']['type'] and
                        scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):

                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - MetaDataOnly amount should have been 1"

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        # Reissue the asset but setting toll address mutability to false
        txid = n0.reissue("BURN_CHECK_1", 0, address0, "", True, -1, "", "", False, 25, "", False, False)
        transaction = n0.gettransaction(txid[0])
        decoded = n0.decoderawtransaction(transaction['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['asm'] == expected_output['scriptPubKey']['asm'] and
                        scriptPubKey['hex'] == expected_output['scriptPubKey']['hex'] and
                        scriptPubKey['reqSigs'] == expected_output['scriptPubKey']['reqSigs'] and
                        scriptPubKey['type'] == expected_output['scriptPubKey']['type'] and
                        scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):

                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - MetaDataOnly amount should have been 1"

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        # Reissue the asset but setting ipfshash to a new hash
        txid = n0.reissue("BURN_CHECK_1", 0, address0, "", True, -1, permanent_ipfs_hash, "", False, 25, "", False, False)
        transaction = n0.gettransaction(txid[0])
        decoded = n0.decoderawtransaction(transaction['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['asm'] == expected_output['scriptPubKey']['asm'] and
                        scriptPubKey['hex'] == expected_output['scriptPubKey']['hex'] and
                        scriptPubKey['reqSigs'] == expected_output['scriptPubKey']['reqSigs'] and
                        scriptPubKey['type'] == expected_output['scriptPubKey']['type'] and
                        scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):

                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - MetaDataOnly amount should have been 1"

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        # Reissue the asset but setting reissue to false
        txid = n0.reissue("BURN_CHECK_1", 0, address0, "", False, -1, permanent_ipfs_hash, "", False, 25, "", False, False)
        transaction = n0.gettransaction(txid[0])
        decoded = n0.decoderawtransaction(transaction['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['asm'] == expected_output['scriptPubKey']['asm'] and
                        scriptPubKey['hex'] == expected_output['scriptPubKey']['hex'] and
                        scriptPubKey['reqSigs'] == expected_output['scriptPubKey']['reqSigs'] and
                        scriptPubKey['type'] == expected_output['scriptPubKey']['type'] and
                        scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):

                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - MetaDataOnly amount should have been 1"

    def reissue_burn_amount_check_100(self):
        self.log.info("Running reissue burn amount check burning 100 EVR")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("BURN_CHECK_100", 1000, address0, "",
                 4, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, False, False)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("BURN_CHECK_100")
        assert_equal(assetdata["name"], "BURN_CHECK_100")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 4)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)

        # Define the expected output data
        expected_output = {
            'value': Decimal('100.00000000'),
            'n': 0,
            'scriptPubKey': {
                'asm': 'OP_DUP OP_HASH160 da61c47adbad4a81e5f14e1fabb3d167a51ca448 OP_EQUALVERIFY OP_CHECKSIG',
                'hex': '76a914da61c47adbad4a81e5f14e1fabb3d167a51ca44888ac',
                'reqSigs': 1,
                'type': 'pubkeyhash',
                'addresses': ['n1ReissueAssetXXXXXXXXXXXXXXWG9NLd']
            }
        }

        # Reissue the asset units 4 -> 8 - should cost 100 EVR
        txid = n0.reissue("BURN_CHECK_100", 0, address0, "", True, 8, "", "", False, 25, "", True, False)
        transaction = n0.gettransaction(txid[0])
        decoded = n0.decoderawtransaction(transaction['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['asm'] == expected_output['scriptPubKey']['asm'] and
                        scriptPubKey['hex'] == expected_output['scriptPubKey']['hex'] and
                        scriptPubKey['reqSigs'] == expected_output['scriptPubKey']['reqSigs'] and
                        scriptPubKey['type'] == expected_output['scriptPubKey']['type'] and
                        scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):

                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - Reissue burn should have been 100"

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        # Reissue the asset increasing the amount & changing the toll amount - should cost 100 EVR
        txid2 = n0.reissue("BURN_CHECK_100", 50, address0, "", True, 8, "", "", True, 25, "", True, False)
        transaction2 = n0.gettransaction(txid[0])
        decoded2 = n0.decoderawtransaction(transaction['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded2['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['asm'] == expected_output['scriptPubKey']['asm'] and
                        scriptPubKey['hex'] == expected_output['scriptPubKey']['hex'] and
                        scriptPubKey['reqSigs'] == expected_output['scriptPubKey']['reqSigs'] and
                        scriptPubKey['type'] == expected_output['scriptPubKey']['type'] and
                        scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):

                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - Reissue burn should have been 100"


    def reissue_toll_address(self):
        self.log.info("Running reissue toll address")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("TOLL_ADDRESS", 1000, address0, "",
                 8, False, True, ipfs_hash, permanent_ipfs_hash, 50, address1, False, True, False)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ADDRESS")
        assert_equal(assetdata["name"], "TOLL_ADDRESS")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)


        # call reissue trying to change:
        # Amount to 1000 + 99
        # Reissue to True
        # Units to 4
        # IPFS Hash to the permanent_ipfs_hash - this should work once tolls is active
        # Toll Amount Mutability to True
        # Toll Amount to 200
        # Toll Address to address2
        address2 = n0.getnewaddress()
        n0.reissue("TOLL_ADDRESS", 99, address0, "", True, 4, permanent_ipfs_hash, "", True, 200, address2, True, True)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # The only things that should have changed are the toll address to address2 and the ipfs_hash
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ADDRESS")
        assert_equal(assetdata["name"], "TOLL_ADDRESS")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address2)

        # reissue toll address to address1 - turn off ability to reissue address
        n0.reissue("TOLL_ADDRESS", 0, address0, "", False, -1, "", "", False, 50, address1, False, False)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # toll address to address1, toll address reissuable should be false
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ADDRESS")
        assert_equal(assetdata["name"], "TOLL_ADDRESS")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)

        # reissue toll address when it is set to false. all settings are false.
        try:
            n0.reissue("TOLL_ADDRESS", 0, address0, "", False, -1, "", "", False, 50, address1, False, False)
        except JSONRPCException as e:
            if "Failed to create reissue asset object. Error: Base: Unable to reissue asset: reissuable is set to false | Amount: Unable to reissue toll amount: reissue toll amount is set to false | Address: Unable to reissue toll address: reissue toll address is set to false" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

    def reissue_permanent_ipfs_hash(self):
        self.log.info("Running reissue permanent ipfs hash")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("REISSUE_PERMANENT", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, True, False)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REISSUE_PERMANENT")
        assert_equal(assetdata["name"], "REISSUE_PERMANENT")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)


        address2 = n0.getnewaddress()

        # call reissue trying to change the permanent_ipfs_hash:
        try:
            n0.reissue("REISSUE_PERMANENT", 0, address0, "", True, -1, "", ipfs_hash, True, 50, address1, True, True)
        except JSONRPCException as e:
            if "Unable to reissue permanent ipfs hash, it is already set" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

    def reissue_ipfs_hash_all_flags_false(self):
        self.log.info("Running reissue ipfs hash all flags false")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("REISSUE_MODIFIABLE_FLAGS_FALSE", 1000, address0, "",
                 8, False, True, ipfs_hash, permanent_ipfs_hash, 50, address1, False, False, False)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REISSUE_MODIFIABLE_FLAGS_FALSE")
        assert_equal(assetdata["name"], "REISSUE_MODIFIABLE_FLAGS_FALSE")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)


        # call reissue trying to change the ipfs_hash:
        address2 = n0.getnewaddress()
        n0.reissue("REISSUE_MODIFIABLE_FLAGS_FALSE", 0, address0, "", False, -1, permanent_ipfs_hash, "", True, 200, address2, False, False)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # The only thing that should have changed is the ipsh_hash
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REISSUE_MODIFIABLE_FLAGS_FALSE")
        assert_equal(assetdata["name"], "REISSUE_MODIFIABLE_FLAGS_FALSE")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)

    def reissue_fails_with_no_changes(self):
        self.log.info("Running reissue fail with no changes")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("REISSUE_FAILS", 1000, address0, "",
                 8, False, True, ipfs_hash, permanent_ipfs_hash, 50, address1, False, False, False)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REISSUE_FAILS")
        assert_equal(assetdata["name"], "REISSUE_FAILS")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)

        # reissue changing nothing, while all reissues flag are false should throw and exception
        try:
            n0.reissue("REISSUE_FAILS", 0, address0, "", False, -1, "", "", True, 200, address1, False, False)
        except JSONRPCException as e:
            if "Failed to create reissue asset object. Error: Base: Unable to reissue asset: reissuable is set to false | Amount: Unable to reissue toll amount: reissue toll amount is set to false | Address: Unable to reissue toll address: reissue toll address is set to false" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

    def reissue_invalid_unit_with_valid_toll_address_change(self):
        self.log.info("Running reissue fail with no changes")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("REISSUE_COMPLEX", 1000, address0, "",
                 4, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, False, True, False)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REISSUE_COMPLEX")
        assert_equal(assetdata["name"], "REISSUE_COMPLEX")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 4)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

        # call reissue trying to change the units to a smaller number, 4 -> 2. Not allowed
        try:
            n0.reissue("REISSUE_COMPLEX", 0, address0, "", True, 2, "", "", False, 0, "", False, True)
        except JSONRPCException as e:
            if "unit must be larger than current unit selection" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

    def reissue_invalid_amount_with_valid_toll_address_change(self):
        self.log.info("Running reissue fail with no changes")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("REISSUE_LARGE_AMOUNT", 20100000000, address0, "",
                 4, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, False, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REISSUE_LARGE_AMOUNT")
        assert_equal(assetdata["name"], "REISSUE_LARGE_AMOUNT")
        assert_equal(assetdata["amount"], 20100000000)
        assert_equal(assetdata["units"], 4)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

        # call reissue trying to issue a qty of assets which would make the total too large.
        try:
            n0.reissue("REISSUE_LARGE_AMOUNT", 1000000000, address0, "", True, -1, "", "", False, 0, "", False, True)
        except JSONRPCException as e:
            if " the amount trying to reissue is to large" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

    def reissue_invalid_ipfs_with_valid_toll_address_change(self):
        self.log.info("Running reissue fail with no changes")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("REISSUE_INVALID_IPFS", 1000, address0, "",
                 4, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, False, True, False)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REISSUE_INVALID_IPFS")
        assert_equal(assetdata["name"], "REISSUE_INVALID_IPFS")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 4)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

        # call reissue trying to change the ipfs to a invalid string
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU"
        try:
            n0.reissue("REISSUE_LARGE_AMOUNT", 0, address0, "", True, -1, ipfs_hash, "", False, 0, "", False, True)
        except JSONRPCException as e:
            if "Invalid IPFS hash (must be 46 characters), Txid hashes (must be 64 characters)" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

    def reissue_toll_assets_big_test(self):
        self.log.info("Running reissue toll assets big test")
        n0 = self.nodes[0]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("TOLL_ASSET", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, True, False)
        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ASSET")
        assert_equal(assetdata["name"], "TOLL_ASSET")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)
        assert_equal(assetdata["remintable"], 0)

        # call reissue setting "reissueable" to false
        n0.reissue("TOLL_ASSET", 50, address0, "", False)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ASSET")
        assert_equal(assetdata["name"], "TOLL_ASSET")
        assert_equal(assetdata["amount"], 1050)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)
        assert_equal(assetdata["remintable"], 0)

        # call reissue changing the ipfs even though reissuable is false
        # We are also changing the toll amount from 50 -> 49
        ipfs_hash_should_change = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AAAA"
        n0.reissue("TOLL_ASSET", 299, address0, "", False, 4, ipfs_hash_should_change, "", True, 49, "", True, True)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ASSET")
        assert_equal(assetdata["name"], "TOLL_ASSET")
        assert_equal(assetdata["amount"], 1050) # Unchanged because reissue is false now even though +299 was requested
        assert_equal(assetdata["units"], 8) # Unchanged because reissue is false now even though set to 4 was requested
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash_should_change) # Changed
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 49) # Changed
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

        address3 = n0.getnewaddress()
        # call reissue changing toll amount but not setting the change bool, and also change the toll address
        n0.reissue("TOLL_ASSET", 0, address0, "", False, 8, "", "", False, 35, address3, True, True)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ASSET")
        assert_equal(assetdata["name"], "TOLL_ASSET")
        assert_equal(assetdata["amount"], 1050)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash_should_change)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 49) # Unchanged because "change_toll_amount" was false
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address3) # Changed

        # reissue, changing the toll amount to a greater amount - should fail; also setting toll_amount_mutability to false
        try:
            n0.reissue("TOLL_ASSET", 0, address0, "", False, 8, "", "", True, 200, "", False, True)
        except JSONRPCException as e:
            if "amount can't be increased" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        # reissue, changing the toll amount to a smaller amount
        n0.reissue("TOLL_ASSET", 0, address0, "", False, 8, "", "", True, 25, "", False, True)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ASSET")
        assert_equal(assetdata["name"], "TOLL_ASSET")
        assert_equal(assetdata["amount"], 1050)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash_should_change)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0) # Changed
        assert_equal(assetdata["toll_amount"], 25) # Changed
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address3)

        # reissue, try to set the toll_amount_mutability back to True
        n0.reissue("TOLL_ASSET", 0, address0, "", False, 8, "", "", True, 200, "", True, True)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ASSET")
        assert_equal(assetdata["toll_amount_mutability"], 0)

        # reissue, set the toll_address_mutability to False and change toll_address to address4
        address4 = n0.getnewaddress()
        n0.reissue("TOLL_ASSET", 0, address0, "", False, 8, "", "", True, 200, address4, False, False)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ASSET")
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address4)

        # reissue, try to reissue toll address back to address3 while all settings are set to false
        try:
            n0.reissue("TOLL_ASSET", 0, address0, "", False, 8, "", "", True, 500, address3, False, False)
        except JSONRPCException as e:
            if "Failed to create reissue asset object. Error: Base: Unable to reissue asset: reissuable is set to false | Amount: Unable to reissue toll amount: reissue toll amount is set to false | Address: Unable to reissue toll address: reissue toll address is set to false" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        # reissue, the permanent ipfs hash which is already set, with all reissue flags set to false
        # This should fail and throw an exception
        permanent_ipfs_hash_getting_changed = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AAAA"
        try:
            n0.reissue("TOLL_ASSET", 0, address0, "", False, 8, "", permanent_ipfs_hash_getting_changed, True, 500, address3, False, False)
        except JSONRPCException as e:
            if "Unable to reissue permanent ipfs hash, it is already set" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_ASSET")
        assert_equal(assetdata["name"], "TOLL_ASSET")
        assert_equal(assetdata["amount"], 1050)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash_should_change)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 25) # Unchanged because toll_amount_mutability is False
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address4) # Changed because toll_address_mutability was True

    def issue_asset_with_toll_info(self):
        self.log.info("Running issue with toll amount")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("ISSUE_TOLL_INFO", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, True, False)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_TOLL_INFO")
        assert_equal(assetdata["name"], "ISSUE_TOLL_INFO")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

    def issue_asset_with_invalid_toll_data(self):
        self.log.info("Running issue with toll amount")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"

        # issue, try to issue toll amount without a toll address
        try:
            n0.issue("ISSUE_TOLL_FAIL", 1000, address0, "",
                     8, True, True, ipfs_hash, permanent_ipfs_hash, 50, "", True, True, False)
        except JSONRPCException as e:
            if "strTollAddress must be provided if toll amount is being set" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        # issue, try to issue toll amount with an invalid toll address
        address2 = n0.getnewaddress()
        badaddress = address2[:-1]
        try:
            n0.issue("ISSUE_TOLL_FAIL", 1000, address0, "",
                     8, True, True, ipfs_hash, permanent_ipfs_hash, 50, badaddress, True, True)
        except JSONRPCException as e:
            if "Invalid Toll Address: Invalid Evrmore address:" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        # issue, try to issue with toll amount = 0 and toll address being set.
        try:
            n0.issue("ISSUE_TOLL_FAIL", 1000, address0, "",
                     8, True, True, ipfs_hash, permanent_ipfs_hash, 0, address2, True, True)
        except JSONRPCException as e:
            if "strTollAddress being set but toll amount is zero" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        # issue, try to issue with invalid permanent hash
        bad_hash = permanent_ipfs_hash[-1]
        try:
            n0.issue("ISSUE_TOLL_FAIL", 1000, address0, "",
                     8, True, True, ipfs_hash, bad_hash, 50, address2, True, True)
        except JSONRPCException as e:
            if "Invalid IPFS hash (must be 46 characters)" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")


    def transfer_toll_asset(self):
        self.log.info("Running issue with toll amount")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("TRANSFER_TOLL_ASSET", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 0.1, address1, True, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TRANSFER_TOLL_ASSET")
        assert_equal(assetdata["name"], "TRANSFER_TOLL_ASSET")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(float(assetdata["toll_amount"]), float(0.1))
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

        address3 = n0.getnewaddress()
        n0.transfer("TRANSFER_TOLL_ASSET", 0.5, address3, "", "", address0, address0)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        n0.transfer("TRANSFER_TOLL_ASSET", 500, address3, "", "", address0, address0)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

    def transfer_toll_asset_to_burn_address(self):
        self.log.info("Running transfer toll to burn address")
        n0, n1 = self.nodes[0], self.nodes[1]

        GLOBAL_BURN_ADDRESS = "n1BurnXXXXXXXXXXXXXXXXXXXXXXU1qejP"
        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("TRANSFER_TOLL_ASSET_BURN", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 0.1, address1, True, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TRANSFER_TOLL_ASSET_BURN")
        assert_equal(assetdata["name"], "TRANSFER_TOLL_ASSET_BURN")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(float(assetdata["toll_amount"]), float(0.1))
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

        address3 = n0.getnewaddress()
        txid = n0.transfer("TRANSFER_TOLL_ASSET_BURN", 0.5, address3, "", "", address0, address0)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        decoded = n0.decoderawtransaction(n0.gettransaction(txid[0])['hex'])

        expected_output = {
            'value': Decimal('0.05000000'),
            'n': 0,
            'scriptPubKey': {
                'asm': 'OP_DUP OP_HASH160 da61c47adbad4a81e5f14e1fabb3d167a51ca448 OP_EQUALVERIFY OP_CHECKSIG',
                'hex': '76a914da61c47adbad4a81e5f14e1fabb3d167a51ca44888ac',
                'reqSigs': 1,
                'type': 'pubkeyhash',
                'addresses': [address1]
            }
        }

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):
                    match_found = True
                    break  # We found a match, no need to continue

        # Check if a match was found
        assert match_found, "No matching output found! - Transfer should have a toll of 0.05 EVR"


        # Now send the same amount to the global burn address, and we need to test to make sure no burn is required
        txid = n0.transfer("TRANSFER_TOLL_ASSET_BURN", 0.5, GLOBAL_BURN_ADDRESS, "", "", address0, address0)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        decoded = n0.decoderawtransaction(n0.gettransaction(txid[0])['hex'])

        # Flag to indicate whether a match was found
        match_found = False

        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == expected_output['value']:
                scriptPubKey = output['scriptPubKey']
                if (scriptPubKey['addresses'] == expected_output['scriptPubKey']['addresses']):
                    match_found = True
                    break  # We found a match, no need to continue

        # Make sure a match wasn't found
        assert not match_found, "Match was found, for the toll to a Global Burn Address when it shouldn't have been"


    def calculate_tolls(self):
        self.log.info("Running issue with toll amount big value")
        n0 = self.nodes[0]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        n0.issue("CALCULATING_TOLLS_1", 5000, address0, "",
                 8, False, False, "", "", 5000000, address1, True, True)

        self.log.info("Waiting for one confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("CALCULATING_TOLLS_1")
        assert_equal(assetdata["name"], "CALCULATING_TOLLS_1")
        assert_equal(assetdata["amount"], 5000)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 5000000)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

        # Calculate the toll for an asset that exists with sending amount set to 1
        result = n0.getcalculatedtoll("CALCULATING_TOLLS_1", 1)
        assert_equal(result["asset_name"], "CALCULATING_TOLLS_1")
        assert_equal(float(result["toll_fee"]), float(5000000))
        assert_equal(result["toll_address"], address1)
        assert_equal(float(result["amount_sending"]), float(1))
        assert_equal(float(result["est_calculated_toll"]), float(5000000))

        # Calculate the toll again but double the amount sent
        result = n0.getcalculatedtoll("CALCULATING_TOLLS_1", 2)
        assert_equal(result["asset_name"], "CALCULATING_TOLLS_1")
        assert_equal(float(result["toll_fee"]), float(5000000))
        assert_equal(result["toll_address"], address1)
        assert_equal(float(result["amount_sending"]), float(2))
        assert_equal(float(result["est_calculated_toll"]), float(10000000))

        # Calculate the toll but no asset name given
        result = n0.getcalculatedtoll("", 1)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(0.1))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(1))
        assert_equal(float(result["est_calculated_toll"]), float(0.1))

        result = n0.getcalculatedtoll("", 0.1)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(0.1))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(0.1))
        assert_equal(float(result["est_calculated_toll"]), float(0.01))

        # Calculated toll is so small, it is reassigned to the MIN_TOLL_AMOUNT 0.000050000
        result = n0.getcalculatedtoll("", 0.001, 0, 0.0001)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(0.0001))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(0.001))
        assert_equal(float(result["est_calculated_toll"]), float(0.00005000))

        # Calculate toll using minimum values for both the transfer qty (1e-8) and the toll fee (1e-8)
        result = n0.getcalculatedtoll("", 0.00000001, 0, 0.00000001)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(0.00000001))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(0.00000001))
        assert_equal(float(result["est_calculated_toll"]), float(0.00005000))

        # Calculate toll using minimum value for the transfer qty (1e-8) and with toll fee = 1
        result = n0.getcalculatedtoll("", 0.00000001, 0, 1)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(1))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(0.00000001))
        assert_equal(float(result["est_calculated_toll"]), float(0.00005000))

        # Calculate toll using small value for the transfer qty (6e-5) and with toll fee = 1
        result = n0.getcalculatedtoll("", 0.00006000, 0, 1)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(1))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(0.00006000))
        assert_equal(float(result["est_calculated_toll"]), float(0.00006000))

        # Sending value, fee is 0.1
        result = n0.getcalculatedtoll("", 5000, 0, 0.1)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(0.1))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(5000))
        assert_equal(float(result["est_calculated_toll"]), float(500))

        # Sending value, fee is 0.35684842
        result = n0.getcalculatedtoll("", 51268, 0, 0.35684842)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(0.35684842))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(51268))
        assert_equal(float(result["est_calculated_toll"]), float(18294.90479656))


        # Sending value, fee is 0.35684842
        result = n0.getcalculatedtoll("", 2100, 0, 5000)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(5000))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(2100))
        assert_equal(float(result["est_calculated_toll"]), float(10500000.0))

        # Sending large value with large fee should hit max and be assigned to MAX_TOLL_AMOUNT
        result = n0.getcalculatedtoll("", 2100, 0, 50000000)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(50000000))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(2100))
        assert_equal(float(result["est_calculated_toll"]), float(1000000000.0))

        # Sending small value with large toll
        result = n0.getcalculatedtoll("", 0.1, 0, 1400000000)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(1400000000))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(0.1))
        assert_equal(float(result["est_calculated_toll"]), float(140000000.0))

        # Sending small value large toll fee
        result = n0.getcalculatedtoll("", 0.0001, 0, 50230005.65168)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(50230005.65168))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(0.0001))
        assert_equal(float(result["est_calculated_toll"]), float(5023.00056516))

        # Sending large value and fee with 8 decimals each
        result = n0.getcalculatedtoll("", 5.98456653, 0, 50230005.65335577)
        assert_equal(result["asset_name"], "")
        assert_equal(float(result["toll_fee"]), float(50230005.65335577))
        assert_equal(result["toll_address"], "")
        assert_equal(float(result["amount_sending"]), float(5.98456653))
        assert_equal(float(result["est_calculated_toll"]), float(300604810.63478374))


    def transfer_toll_asset_two_nodes(self):
        self.log.info("Running transfer toll asset two nodes")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("TRANSFER_TOLL_ASSET2", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 0.1, address1, True, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TRANSFER_TOLL_ASSET2")
        assert_equal(assetdata["name"], "TRANSFER_TOLL_ASSET2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(float(assetdata["toll_amount"]), float(0.1))
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

        evraddress = n1.getnewaddress()
        addresswithone = n1.getnewaddress()
        n0.transfer("TRANSFER_TOLL_ASSET2", 1.0, addresswithone, "", "", address0, address0)

        addresswiththree = n1.getnewaddress()
        n0.transfer("TRANSFER_TOLL_ASSET2", 3.0, addresswiththree, "", "", address0, address0)

        # n1 needs EVR for gas
        n0.sendtoaddress(evraddress, 100)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        changeaddress = n1.getnewaddress()
        n1.transfer("TRANSFER_TOLL_ASSET2", 4, addresswithone, "", "", changeaddress, changeaddress)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        # Uncomment to test toll adjustments in the logs
        # assert(False)

    def toll_transfer_custom_transactions(self):
        self.log.info("Running toll_transfer_custom_transactions")
        n0, n1 = self.nodes[0], self.nodes[1]

        address0 = n0.getnewaddress()	# evr_source_addr
        address1 = n0.getnewaddress()	# asset source_addr
        address2 = n0.getnewaddress()	# toll_pay_addr
        address3 = n0.getnewaddress()   # asset_dest_addr
        GLOBAL_BURN_ADDRESS = "n1BurnXXXXXXXXXXXXXXXXXXXXXXU1qejP"

        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"

        self.log.info("Issuing assets with issue()")
        txid_issue = n0.issue("TOLL_PAY_CHECK", 1000, address1, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 0.1, address2, True, True, False)
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("TOLL_PAY_CHECK")
        assert_equal(assetdata["name"], "TOLL_PAY_CHECK")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(float(assetdata["toll_amount"]), float(0.1))
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address2)
        self.log.info("Verified that toll asset info is correct after issuing.")

        self.log.info("Sending EVR with sendtoaddress()")
        txid_send = n0.sendtoaddress(address0, 5)
        n0.generate(1)
        self.sync_all()
        decoded = n0.decoderawtransaction(n0.gettransaction(txid_send)['hex'])
        # Iterate over the outputs and compare with the expected output; "send_index" is the output which contains our stash of EVR
        for output in decoded['vout']:
            if output['value'] == Decimal('5.00000000'):
                send_index = output['n']
                break  # We found a match, no need to continue

        #txid_transfer = n0.transfer("TOLL_PAY_CHECK", 0.5, address3, "", "", address0, address1)
        #    which created: "0200000004767406332966cfd00c9246ae80ad18ccd57552ce35f8120e6fb3515969bebfdf000000006b483045022100be57f34f9bcab5f3b3b979e0edd9f6af1526a1b96dfd2cab9e62e958f47299730220422eef6c5c5eaee99748fd6893e33a9828ab048b291bad19e8dc316dccfe3f88012103c99a1532f534cf78e544c1464ccd8d13b725ba7ade6d72db05c813e1a5d3b551feffffff81d4d028ee3f3ba2a30402f13ec1451fd79a807d2ec063f9673eac51623dcc34000000006a473044022027a179e8871c47e9c3f0560a4005e2a41ef3db8cc703101779ddcd9ada3d80d0022070285006c8b56fe19660f7f457d7bba5bbce91c03a64433716d56e3c7269e654012103c99a1532f534cf78e544c1464ccd8d13b725ba7ade6d72db05c813e1a5d3b551feffffff9ca9bac4bfb1307d4d032715fdfa01a57a6762b266fc10db666a9999ed8b4035000000006a47304402206a8f5b799be22ff5cbe67e167404f36caa1d34f75240e2bfc0b940a98b211cbe02205263e607a11b010e4837d52d6c8ea04d984ae74af3145dc5e126b0b9a4d8a149012103c99a1532f534cf78e544c1464ccd8d13b725ba7ade6d72db05c813e1a5d3b551feffffff8c6b4e0be4070c928776d875a22b4fef3ead6b6c58b679704f58c0babba1921b030000006a4730440220041e7c9b75453b0ea55458c4a1c95ec47947ac3014369d70e8d9302d1ba1aeef022060278abb4a6d078e14bb31d45cc333a5b5849de0c278b72f020793974eddc828012102df91ec8eab3566e3d12f290dfcb4d55e6be587f6168c397723746357af4b6888feffffff0400000000000000003776a9140de9133dfd378605945a1dac5814b29db98639a088acc01b657672740e544f4c4c5f5041595f434845434b80f0fa020000000075404b4c00000000001976a91413a5a6932d302cedb693c6a5ead9508d8c8db58388aca7541000000000001976a91430ca8b7e51f749d1187d223b3dfbb6460a64046f88ac00000000000000003776a9143291729b6ea2500e5f198a768ca6d2e7eb99904188acc01b657672740e544f4c4c5f5041595f434845434b80f77b451700000075bc0b0000"
        raw_txn0 = n0.createrawtransaction([{"txid":txid_send,"vout":send_index},{"txid":txid_issue[0],"vout":3}], {GLOBAL_BURN_ADDRESS:{"transfer":{"TOLL_PAY_CHECK":0.5}}, address0: 0.7, address2: 0.05, address1:{"transfer":{"TOLL_PAY_CHECK":999.5}}})
        #    which created: "02000000023c3132d072a92bb0c929740e622dafc5ef9ff984cd3742660309ee0ab40c37ec0000000000ffffffffba516c067ce8e4e115195b315dd7f58998448bb89e215c9c1600828021c38a1b0300000000ffffffff0400000000000000003776a91428db1b633b7805a3c5075bf04fbb49646e06a0e488acc01b657672740e544f4c4c5f5041595f434845434b80f0fa020000000075801d2c04000000001976a91486e303fef25216f137ecddd6acf13208ad7958e288ac404b4c00000000001976a91417e630a40ca611c12adf79913356a0d84d796a8e88ac00000000000000003776a914aed16492e144a37d9634879a5913c8ab2397bb1388acc01b657672740e544f4c4c5f5041595f434845434b80f77b45170000007500000000"

        raw_inputs = raw_txn0[:raw_txn0.find("ffffffff", raw_txn0.find("ffffffff") + 8) + 8]

        script_evr_source_addr = n0.validateaddress(address0)['scriptPubKey']
        script_asset_source_addr = n0.validateaddress(address1)['scriptPubKey']
        script_toll_pay_addr = n0.validateaddress(address2)['scriptPubKey']
        script_asset_dest_addr = n0.validateaddress(address3)['scriptPubKey']
        script_global_burn_addr = "76a914d7c8944771bbfe427418f27320e72a1322faf13488ac"                

        NINE_NINE_NINE_POINT_FIVE =  "80f77b4517000000"   # 999.5
        NINE_NINE_NINE = "0007814217000000"   # 999
        NINE_NINE_EIGHT_POINT_FIVE =  "8016863f17000000"   # 998.5
        ONE = "00e1f50500000000"  # 1
        POINT_SEVEN = "801d2c0400000000"  # 0.7
        POINT_FIVE =  "80f0fa0200000000"  # 0.5
        POINT_ONE = "8096980000000000"  # 0.1
        POINT_ZERO_FIVE = "404b4c0000000000"    # 0.05
        ZERO = "0000000000000000"   # 0

        out_evr_change = POINT_SEVEN + "19" + script_evr_source_addr
        out_toll_payment = POINT_ZERO_FIVE + "19" + script_toll_pay_addr
        out_asset_transfer = ZERO + "37" +  script_asset_dest_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + POINT_FIVE + "75"
        out_asset_burn = ZERO + "37" +  script_global_burn_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + POINT_FIVE + "75"
        out_asset_change = ZERO + "37" + script_asset_source_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + NINE_NINE_NINE + "75"
        out_end  = "00000000"
        raw_outputs = "05" + out_asset_transfer + out_toll_payment + out_evr_change + out_asset_change + out_asset_transfer + out_end
        raw_txn = raw_inputs + raw_outputs
        signed_raw_txn = n0.signrawtransaction(raw_txn)
        #n0.sendrawtransaction(signed_raw_txn['hex'])
        assert_raises_rpc_error(-26, "bad-txns-insufficient-toll-paid", n0.sendrawtransaction, signed_raw_txn['hex'])
        n0.generate(1)
        self.sync_all()
        self.log.info("Verified that transaction fails if it contains 2 toll-asset transfer outputs but only 1 toll payment output")

        out_evr_change = POINT_SEVEN + "19" + script_evr_source_addr
        out_toll_payment = POINT_ZERO_FIVE + "19" + script_toll_pay_addr
        out_asset_transfer = ZERO + "37" +  script_asset_dest_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + POINT_FIVE + "75"
        out_asset_burn = ZERO + "37" +  script_global_burn_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + POINT_FIVE + "75"
        out_asset_change = ZERO + "37" + script_asset_source_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + NINE_NINE_NINE + "75"
        out_end  = "00000000"
        raw_outputs = "04" + out_asset_transfer + out_asset_burn + out_evr_change + out_asset_change + out_end
        raw_txn = raw_inputs + raw_outputs
        signed_raw_txn = n0.signrawtransaction(raw_txn)
        #n0.sendrawtransaction(signed_raw_txn['hex'])
        assert_raises_rpc_error(-26, "bad-txns-insufficient-toll-paid", n0.sendrawtransaction, signed_raw_txn['hex'])
        n0.generate(1)
        self.sync_all()
        self.log.info("Verified that transaction fails if it contains both a toll-asset transfer output and a toll-asset burn output but no toll payment output")

        out_evr_change = POINT_SEVEN + "19" + script_evr_source_addr
        out_toll_payment = POINT_ZERO_FIVE + "19" + script_toll_pay_addr
        out_asset_transfer = ZERO + "37" +  script_asset_dest_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + POINT_FIVE + "75"
        out_asset_burn = ZERO + "37" +  script_global_burn_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + POINT_FIVE + "75"
        out_asset_change = ZERO + "37" + script_asset_source_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + NINE_NINE_NINE + "75"
        out_end  = "00000000"
        raw_outputs = "04" + out_asset_burn + out_evr_change + out_asset_change + out_asset_transfer + out_end
        raw_txn = raw_inputs + raw_outputs
        signed_raw_txn = n0.signrawtransaction(raw_txn)
        #n0.sendrawtransaction(signed_raw_txn['hex'])
        assert_raises_rpc_error(-26, "bad-txns-insufficient-toll-paid", n0.sendrawtransaction, signed_raw_txn['hex'])
        n0.generate(1)
        self.sync_all()
        self.log.info("Verified that transaction still fails if the toall-asset burn output comes first and the toll-asset transfer output at the end with no toll payment output")

        # Standard test with one toll-asset transfer and one toll payment (for reference- should pass)
        out_evr_change = POINT_SEVEN + "19" + script_evr_source_addr
        out_toll_payment = POINT_ZERO_FIVE + "19" + script_toll_pay_addr
        out_asset_transfer = ZERO + "37" +  script_asset_dest_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + POINT_FIVE + "75"
        out_asset_change = ZERO + "37" + script_asset_source_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + NINE_NINE_NINE_POINT_FIVE + "75"
        out_end  = "00000000"
        raw_outputs = "04" + out_asset_transfer + out_toll_payment + out_evr_change + out_asset_change + out_end
        raw_txn = raw_inputs + raw_outputs
        signed_raw_txn = n0.signrawtransaction(raw_txn)
        n0.sendrawtransaction(signed_raw_txn['hex'])
        n0.generate(1)
        self.sync_all()
        self.log.info("Verified functional standard transaction with 1 toll-asset transfer output and 1 toll payment output")

        address0 = n0.getnewaddress()	# evr_source_addr
        address1 = n0.getnewaddress()	# asset source_addr
        address2 = n0.getnewaddress()	# toll_pay_addr
        address3 = n0.getnewaddress()   # asset_dest_addr

        self.log.info("Issuing assets with issue()")
        txid_issue = n0.reissue("TOLL_PAY_CHECK", 1000, address1, "",
                 True, 8, ipfs_hash, "", False , 0.1, address2, True, True)
        n0.generate(1)
        self.sync_all()

        self.log.info("Sending EVR with sendtoaddress()")
        txid_send = n0.sendtoaddress(address0, 5)
        n0.generate(1)
        self.sync_all()
        decoded = n0.decoderawtransaction(n0.gettransaction(txid_send)['hex'])
        # Iterate over the outputs and compare with the expected output
        for output in decoded['vout']:
            if output['value'] == Decimal('5.00000000'):
                send_index = output['n']
                break  # We found a match, no need to continue

        raw_txn0 = n0.createrawtransaction([{"txid":txid_send,"vout":send_index},{"txid":txid_issue[0],"vout":3}], {GLOBAL_BURN_ADDRESS:{"transfer":{"TOLL_PAY_CHECK":0.5}}, address0: 0.7, address2: 0.05, address1:{"transfer":{"TOLL_PAY_CHECK":999.5}}})
        raw_inputs = raw_txn0[:raw_txn0.find("ffffffff", raw_txn0.find("ffffffff") + 8) + 8]
        script_evr_source_addr = n0.validateaddress(address0)['scriptPubKey']
        script_asset_source_addr = n0.validateaddress(address1)['scriptPubKey']
        script_toll_pay_addr = n0.validateaddress(address2)['scriptPubKey']
        script_asset_dest_addr = n0.validateaddress(address3)['scriptPubKey']

        # Test with 2 toll-asset transfers and 2 toll payments (should pass)
        out_evr_change = POINT_SEVEN + "19" + script_evr_source_addr
        out_toll_payment = POINT_ZERO_FIVE + "19" + script_toll_pay_addr
        out_asset_transfer = ZERO + "37" +  script_asset_dest_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + POINT_FIVE + "75"
        out_asset_burn = ZERO + "37" +  script_global_burn_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + POINT_FIVE + "75"
        out_asset_change = ZERO + "37" + script_asset_source_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + NINE_NINE_EIGHT_POINT_FIVE + "75"
        #out_asset_change = ZERO + "37" + script_asset_source_addr + "c01b657672740e544f4c4c5f5041595f434845434b" + NINE_NINE_NINE + "75"        
        out_end  = "00000000"
        raw_outputs = "07" + out_asset_transfer + out_toll_payment + out_evr_change + out_asset_change + out_asset_transfer + out_toll_payment + out_asset_burn + out_end
        #raw_outputs = "06" + out_asset_transfer + out_toll_payment + out_evr_change + out_asset_change + out_asset_transfer + out_toll_payment + out_end
        raw_txn = raw_inputs + raw_outputs
        signed_raw_txn = n0.signrawtransaction(raw_txn)
        n0.sendrawtransaction(signed_raw_txn['hex'])
        n0.generate(1)
        self.sync_all()
        self.log.info("Verified functional transaction with 2 toll-asset transfer outputs and 2 toll payment outputs and 1 toll asset burn")

        #decoded_txid_issue = n0.decoderawtransaction(n0.gettransaction(txid_issue[0])['hex'])
        #decoded_txid_send = n0.decoderawtransaction(n0.gettransaction(txid_send)['hex'])
        #decoded_txid_transfer = n0.decoderawtransaction(n0.gettransaction(txid_transfer[0])['hex'])
        #decoded_raw_txn = n0.decoderawtransaction(signed_raw_txn['hex'])
        #decoded = decoded_txid_transfer

    def updatemetadata_all(self):
        self.log.info("Running updatemetadata all")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("UPDATE_META_DATA", 1000, address0, "",
                 8, False, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, True)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA")
        assert_equal(assetdata["name"], "UPDATE_META_DATA")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)


        # call updatemetadata trying to change:
        # IPFS Hash to the permanent ipfs hash
        # Toll Address to address2
        # Toll Amount to 30
        # Toll Amount Mutability to False
        address2 = n0.getnewaddress()
        n0.updatemetadata("UPDATE_META_DATA", "", permanent_ipfs_hash, "", address2, True, 30, False, True)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # All the requested changes should have happened
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA")
        assert_equal(assetdata["name"], "UPDATE_META_DATA")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 30)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address2)

    def updatemetadata_ipfs_only(self):
        self.log.info("Running updatemetadata ipfs only")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("UPDATE_META_DATA_2", 1, address0, "",
                 8, False, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, True)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_2")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_2")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)


        # call updatemetadata trying to change:
        # IPFS Hash to a new hash
        new_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr48888"
        n0.updatemetadata("UPDATE_META_DATA_2", "", new_ipfs_hash, "", "", False, 50, True, True)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # The only thing that should have changed is the ipfs hash
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_2")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_2")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

    def updatemetadata_permanent_ipfs_hash_already_set(self):
        self.log.info("Running updatemetadata permanent ipfs already set")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("UPDATE_META_DATA_3", 1, address0, "",
                 8, False, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, True)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_3")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_3")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)


        # call updatemetadata trying to change:
        # Permanent IPFS Hash to a new hash
        new_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr48888"

        try:
            n0.updatemetadata("UPDATE_META_DATA_3", "", "", new_ipfs_hash, "", True, 50, True, True)
        except JSONRPCException as e:
            if "Unable to reissue permanent ipfs hash, it is already set" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

    def updatemetadata_permanent_ipfs_hash_not_set(self):
        self.log.info("Running updatemetadata permanent ipfs not set")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        n0.issue("UPDATE_META_DATA_4", 1, address0, "",
                 8, False, True, ipfs_hash, "", 50, address1, True, True)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_4")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_4")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)


        # call updatemetadata trying to set the permanent ipfs hash:
        # Permanent IPFS Hash to a new hash
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.updatemetadata("UPDATE_META_DATA_4", "", "", permanent_ipfs_hash, "", True, 50, True, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_4")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_4")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

    def updatemetadata_change_toll_address(self):
        self.log.info("Running updatemetadata change toll address")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        n0.issue("UPDATE_META_DATA_5", 1, address0, "",
                 8, False, True, ipfs_hash, "", 50, address1, True, True)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_5")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_5")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)


        # call updatemetadata trying to change the toll address
        new_toll_address = n0.getnewaddress()
        n0.updatemetadata("UPDATE_META_DATA_5", "", "", "", new_toll_address, True, 50, True, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_5")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_5")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], new_toll_address)

    def updatemetadata_change_toll_address_mutability_off(self):
        self.log.info("Running updatemetadata change toll address mutability off")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        n0.issue("UPDATE_META_DATA_6", 1, address0, "",
                 8, False, True, ipfs_hash, "", 50, address1, True, False)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_6")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_6")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)


        # call updatemetadata trying to set the toll address, but it won't be changed because toll_address_mutability is False
        new_toll_address = n0.getnewaddress()
        n0.updatemetadata("UPDATE_META_DATA_6", "", "", "", new_toll_address, True, 50, True, False)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_6")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_6")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], address1)

    def updatemetadata_change_toll_amount(self):
        self.log.info("Running updatemetadata change toll amount")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        n0.issue("UPDATE_META_DATA_7", 1, address0, "",
                 8, False, True, ipfs_hash, "", 50, address1, False, True)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_7")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_7")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)


        # call updatemetadata trying to set the toll amount, but it won't be changed because toll_amount_mutability is False
        new_toll_address = n0.getnewaddress()
        n0.updatemetadata("UPDATE_META_DATA_7", "", "", "", "", True, 30, False, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_7")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_7")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

    def updatemetadata_change_toll_amount_mutability_off(self):
        self.log.info("Running updatemetadata change toll amount mutability off")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        n0.issue("UPDATE_META_DATA_8", 1, address0, "",
                 8, False, True, ipfs_hash, "", 50, address1, False, True)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_8")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_8")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)


        # call updatemetadata trying to change the toll amount, but it won't be changed because toll_amount_mutability is False
        new_toll_address = n0.getnewaddress()
        n0.updatemetadata("UPDATE_META_DATA_8", "", "", "", "", True, 30, False, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("UPDATE_META_DATA_8")
        assert_equal(assetdata["name"], "UPDATE_META_DATA_8")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)

    def issue_reissue_v1_v2_version_checks(self):
        self.log.info("Running issue reissue version checks")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"

        n0.issue("ISSUE_STANDARD_VERSION", 1000, address0, "",
                 8, True, True, ipfs_hash, "", 0, "", False, False, False)


        n0.issue("ISSUE_TOLL_VERSION", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 50, address1, True, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_STANDARD_VERSION")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "ISSUE_STANDARD_VERSION")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_TOLL_VERSION")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "ISSUE_TOLL_VERSION")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 50)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], address1)
        assert_equal(assetdata["remintable"], 1)

        # call reissue adding more assets, and changing the ipfshash
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv999"
        n0.reissue("ISSUE_STANDARD_VERSION", 105, address0, "", True, -1, new_ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # The version should upgrade
        # amount is changed, ipfs_hash is changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_STANDARD_VERSION")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "ISSUE_STANDARD_VERSION")
        assert_equal(assetdata["amount"], 1105)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 1)

        # call reissue again changing reissueable to False
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv888"
        n0.reissue("ISSUE_STANDARD_VERSION", 0, address0, "", False, -1, new_ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # call reissue, change the ipfshash again, and set permanent_ipfs_hash
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv666"
        n0.reissue("ISSUE_STANDARD_VERSION", 0, address0, "", False, -1, new_ipfs_hash, permanent_ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # the ipfs_hash changed and the permanent_ipfs_hash was set even with "reissuable"=0
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_STANDARD_VERSION")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "ISSUE_STANDARD_VERSION")
        assert_equal(assetdata["amount"], 1105)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 1)


    def issue_ipfs_non_reissuable_permanent_ipfshash(self):
        self.log.info("Running issue with ipfshash non reissuable, permanent hash test")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"

        n0.issue("ISSUE_IPFS_PERMANENT_TEST", 1000, address0, "",
                 8, False, True, ipfs_hash, "", 0, "", False, False, False)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        # the permanent_ipfs_hash is automatically set to be the same as ipfs_hash
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_IPFS_PERMANENT_TEST")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "ISSUE_IPFS_PERMANENT_TEST")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)

        # call reissue adding more assets, and changing the ipfshash
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv999"
        n0.reissue("ISSUE_IPFS_PERMANENT_TEST", 105, address0, "", True, -1, new_ipfs_hash, new_ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # The version should upgrade
        # ipfs hash is set to the new one from the reissue
        # permanent hash remains the same as the previous ipfs_hash; the request to change it has no effect and generates no error
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_IPFS_PERMANENT_TEST")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "ISSUE_IPFS_PERMANENT_TEST")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)

        # call reissue and changing the ipfshash again,
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv888"
        permanent_ipfs_hash_test = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        assert_raises_rpc_error(-25, "Failed to create reissue asset object. Error: Unable to reissue permanent ipfs hash, it is already set.", n0.reissue, "ISSUE_PERMANENT_IPFS_TRUE", 0, address0, "", True, -1, new_ipfs_hash, permanent_ipfs_hash_test)
        # n0.reissue("ISSUE_PERMANENT_IPFS_TRUE", 0, address0, "", True, -1, new_ipfs_hash, permanent_ipfs_hash_test)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

    def issue_reissue_permanent_ipfs_mutability_when_reissue_true(self):
        self.log.info("Running issue reissue permanent ipfs mutability reissue is true")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"

        n0.issue("ISSUE_PERMANENT_IPFS_TRUE", 1000, address0, "",
                 8, True, True, ipfs_hash, "", 0, "", False, False, False)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue adding more assets, and changing the ipfshash
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv999"
        n0.reissue("ISSUE_PERMANENT_IPFS_TRUE", 105, address0, "", True, -1, new_ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # amount is change, ipfs_hash is changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["amount"], 1105)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue with changing the ipfshash again,
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv888"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.reissue("ISSUE_PERMANENT_IPFS_TRUE", 0, address0, "", True, -1, new_ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # ipfs_hash is changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["amount"], 1105)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue and changing the ipfshash again
        # Disable reissue
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv777"
        n0.reissue("ISSUE_PERMANENT_IPFS_TRUE", 0, address0, "", False, -1, new_ipfs_hash, "")

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # ipfs_hash is changed and "reissueable=False"
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["amount"], 1105)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reisssue changing ipfs_hash again and setting permanent_ipfs_hash
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv777"
        n0.reissue("ISSUE_PERMANENT_IPFS_TRUE", 0, address0, "", False, -1, new_ipfs_hash, permanent_ipfs_hash)
        n0.generate(1)
        self.sync_all()

        # ipfs_hash is changed and permanent_ipfs_hash is set
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "ISSUE_PERMANENT_IPFS_TRUE")
        assert_equal(assetdata["amount"], 1105)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue trying to change the permanent ipfs hash
        try:
            wont_work_ipfs = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv666"
            n0.reissue("ISSUE_PERMANENT_IPFS_TRUE", 0, address0, "", False, -1, "", wont_work_ipfs)
        except JSONRPCException as e:
            if "Failed to create reissue asset object. Error: Unable to reissue permanent ipfs hash, it is already set" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

    def issue_reissue_permanent_ipfs_mutability_when_reissue_false(self):
        self.log.info("Running issue reissue permanent ipfs mutability reissue is true")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        address1 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        new_ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv999"
        new_ipfs_hash2 = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv888"       
        new_ipfs_hash3 = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv777"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        wont_work_ipfs = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zv666"

        # Variation #1: - no initial ipfs_hash
        #   non-reissuable, ipfs_hash = ""
        #   LEGACY_NO_IPFS_REISS_FALSE
        #   check the metadata
        #   set the ipfs_hash
        #   check the metadata (permanent_ipfs_hash remains unset)
        #   try setting just the permanent_ipfs_hash
        #   catch the exception

        #n0.issue("LEGACY_NO_IPFS_REISS_FALSE", 1000, address0, "", 8, False, False, "", "", 0, "", False, False, False)
        # Moved the "issue" to issue_legacy_assets() just as confirmation that issuing pre-toll-fork assets behaves identically to 
        #     issuing assets post-toll-fork which use none of the new assets metadata fields.

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_NO_IPFS_REISS_FALSE")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_NO_IPFS_REISS_FALSE")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"],0)
        assert_equal(assetdata["has_ipfs"], 0)
        #assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue setting the ipfs_hash
        n0.reissue("LEGACY_NO_IPFS_REISS_FALSE", 0, address0, "", False, -1, ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # ipfs_hash is changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_NO_IPFS_REISS_FALSE")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_NO_IPFS_REISS_FALSE")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue and try to change only the permanent_ipfs_hash
        try:
            n0.reissue("LEGACY_NO_IPFS_REISS_FALSE", 0, address0, "", False, -1, "", permanent_ipfs_hash)
        except JSONRPCException as e:
            #if "Failed to create reissue asset object. Error: Unable to reissue permanent ipfs hash, it is already set" not in e.error['message']:
            if "Failed to create reissue asset object. Error: Base: Unable to reissue asset: reissuable is set to false" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # nothing should have changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_NO_IPFS_REISS_FALSE")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_NO_IPFS_REISS_FALSE")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        ##===========

        # Variation #2:  - no initial ipfs_hash
        #   non-reissuable, ipfs_hash = ""
        #   LEGACY_NO_IPFS_REISS_FALSE_2
        #   check the metadata
        #   try setting just the permanent_ipfs_hash
        #   catch the exception

        #n0.issue("LEGACY_NO_IPFS_REISS_FALSE_2", 1000, address0, "", 8, False, False, "", "", 0, "", False, False, False)
        # Moved the "issue" to issue_legacy_assets() just as confirmation that issuing pre-toll-fork assets behaves identically to 
        #     issuing assets post-toll-fork which use none of the new assets metadata fields.


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_NO_IPFS_REISS_FALSE_2")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_NO_IPFS_REISS_FALSE_2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"],0)
        assert_equal(assetdata["has_ipfs"], 0)
        #assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue and try to change the permanent_ipfs_hash
        try:
            n0.reissue("LEGACY_NO_IPFS_REISS_FALSE_2", 0, address0, "", False, -1, "", wont_work_ipfs)
        except JSONRPCException as e:
            #if "Failed to create reissue asset object. Error: Unable to reissue permanent ipfs hash, it is already set" not in e.error['message']:
            if "Failed to create reissue asset object. Error: Base: Unable to reissue asset: reissuable is set to false" not in e.error['message']:

                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # nothing should have changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_NO_IPFS_REISS_FALSE_2")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_NO_IPFS_REISS_FALSE_2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 0)
        #assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        ##============

        # Variation #3: - no initial ipfs_hash
        #   non-reissuable, ipfs_hash = ""
        #   LEGACY_NO_IPFS_REISS_FALSE_3
        #   check the metadata
        #   set the ipfs_hash
        #   check the metadata (ipfs_hash is set, permanent_ipfs_hash remains unset)
        #   set the ipfs_hash and permanent_ipfs_hash (to different values)
        #   check the metadata (both got set as requested)
        #   try setting just the permanent_ipfs_hash
        #   catch the exception

        #n0.issue("LEGACY_NO_IPFS_REISS_FALSE_3", 1000, address0, "", 8, False, False, "", "", 0, "", False, False, False)
        # Moved the "issue" to issue_legacy_assets() just as confirmation that issuing pre-toll-fork assets behaves identically to 
        #     issuing assets post-toll-fork which use none of the new assets metadata fields.


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_NO_IPFS_REISS_FALSE_3")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_NO_IPFS_REISS_FALSE_3")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"],0)
        assert_equal(assetdata["has_ipfs"], 0)
        #assert_equal(assetdata["ipfs_hash"], "")
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue setting the ipfs_hash
        n0.reissue("LEGACY_NO_IPFS_REISS_FALSE_3", 0, address0, "", False, -1, ipfs_hash, "")

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # ipfs_hash is changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_NO_IPFS_REISS_FALSE_3")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_NO_IPFS_REISS_FALSE_3")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue setting both the ipfs_hash and the permanent_ipfs_hash
        n0.reissue("LEGACY_NO_IPFS_REISS_FALSE_3", 0, address0, "", False, -1, new_ipfs_hash, permanent_ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # both ipfs_hash and permanent_ipfs_hash should have changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_NO_IPFS_REISS_FALSE_3")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_NO_IPFS_REISS_FALSE_3")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue and try to change the permanent_ipfs_hash again
        try:
            n0.reissue("LEGACY_NO_IPFS_REISS_FALSE_3", 0, address0, "", False, -1, "", wont_work_ipfs)
        except JSONRPCException as e:
            if "Failed to create reissue asset object. Error: Unable to reissue permanent ipfs hash, it is already set" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # nothing should have changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_NO_IPFS_REISS_FALSE_3")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_NO_IPFS_REISS_FALSE_3")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        ##============

        # Variation #4: - initial "ipfs_hash" = ipfs_hash
        #   non-reissuable, "ipfs_hash" = ipfs_hash
        #   LEGACY_W_IPFS_REISS_FALSE
        #   check the metadata (permanent_ipfs_hash is already same as ipfs_hash)
        #   change ipfs_hash to new_ipfs_hash
        #   check the metadata (ipfs_hash changes, permanent_ipfs_hash does not)
        #   try changing just the permanent_ipfs_hash to permanent_ipfs_hash
        #   catch the exception
        #   check the metadata (nothing should have changed)

        #n0.issue("LEGACY_W_IPFS_REISS_FALSE", 1000, address0, "", 8, False, True, ipfs_hash, "", 0, "", False, False, False)
        # Moved the "issue" to issue_legacy_assets() just as confirmation that issuing pre-toll-fork assets behaves identically to 
        #     issuing assets post-toll-fork which use none of the new assets metadata fields.

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_W_IPFS_REISS_FALSE")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_W_IPFS_REISS_FALSE")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"],0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue changing the ipfs_hash to new_ipfs_hash
        n0.reissue("LEGACY_W_IPFS_REISS_FALSE", 0, address0, "", False, -1, new_ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # ipfs_hash is changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_W_IPFS_REISS_FALSE")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_W_IPFS_REISS_FALSE")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue trying to change only the permanent_ipfs_hash
        try:
            n0.reissue("LEGACY_W_IPFS_REISS_FALSE", 0, address0, "", False, -1, "", wont_work_ipfs)
        except JSONRPCException as e:
            if "Failed to create reissue asset object. Error: Unable to reissue permanent ipfs hash, it is already set" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # nothing should have changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_W_IPFS_REISS_FALSE")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_W_IPFS_REISS_FALSE")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        ##============

        # Variation #5: - initial "ipfs_hash" = ipfs_hash
        #   non-reissuable, "ipfs_hash" = ipfs_hash
        #   LEGACY_W_IPFS_REISS_FALSE_2
        #   check the metadata (permanent_ipfs_hash is already same as ipfs_hash)
        #   Try changing the ipfs_hash and permanent_ipfs_hash (to different values- new_ipfs_hash & permanent_ipfs_hash respectively); no error
        #   check the metadata (only the ipfs_hash changed)
        #   Try changing the ipfs_hash and permanent_ipfs_hash (to different values- new_ipfs_hash2 & permanent_ipfs_hash respectively)
        #   catch the exception

        #n0.issue("LEGACY_W_IPFS_REISS_FALSE_2", 1000, address0, "", 8, False, True, ipfs_hash, "", 0, "", False, False, False)
        # Moved the "issue" to issue_legacy_assets() just as confirmation that issuing pre-toll-fork assets behaves identically to 
        #     issuing assets post-toll-fork which use none of the new assets metadata fields.

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_W_IPFS_REISS_FALSE_2")
        assert_equal(assetdata["version"], "1")
        assert_equal(assetdata["name"], "LEGACY_W_IPFS_REISS_FALSE_2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"],0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue changing the ipfs_hash to new_ipfs_hash and  permanent_ipfs_hash to  permanent_ipfs_hash; note no error
        n0.reissue("LEGACY_W_IPFS_REISS_FALSE_2", 0, address0, "", False, -1, new_ipfs_hash, permanent_ipfs_hash)

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

        # only ipfs_hash is changed
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_W_IPFS_REISS_FALSE_2")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["name"], "LEGACY_W_IPFS_REISS_FALSE_2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], new_ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 0)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 0)
        assert_equal(assetdata["toll_address"], "")

        # call reissue trying to change both ipfs_hash and permanent_ipfs_hash
        try:
            n0.reissue("LEGACY_W_IPFS_REISS_FALSE", 0, address0, "", False, -1, new_ipfs_hash2, wont_work_ipfs)
        except JSONRPCException as e:
            if "Failed to create reissue asset object. Error: Unable to reissue permanent ipfs hash, it is already set" not in e.error['message']:
                raise AssertionError("Expected substring not found:" + e.error['message'])
        except Exception as e:
            raise AssertionError("Unexpected exception raised: " + type(e).__name__)
        else:
            raise AssertionError("No exception raised")

        self.log.info("Waiting for ten confirmations after reissue...")
        n0.generate(1)
        self.sync_all()

    def issue_unique_asset_with_toll_info_and_transfer(self):
        self.log.info("Running issue with toll amount")
        n0, n1 = self.nodes[0], self.nodes[1]

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        ipfs_hash = "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8"
        permanent_ipfs_hash = "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E"
        n0.issue("ISSUE_ROOT_ASSET", 1000, address0, "",
                 8, True, True, ipfs_hash, permanent_ipfs_hash, 0, "", True, True, False)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("ISSUE_ROOT_ASSET")
        assert_equal(assetdata["name"], "ISSUE_ROOT_ASSET")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 8)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["ipfs_hash"], ipfs_hash)
        assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hash)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(assetdata["toll_amount"], 0)
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], "")

        asset_tags = []
        to_address = address0
        change_address = ""
        ipfs_hashes = []
        permanent_ipfs_hashes = []
        toll_address = n1.getnewaddress()
        toll_amount = 1

        # Loop 10 times to add TAG1 to TAG10
        for i in range(0, 10):
            asset_tags.append(f"TAG{i+1}")
            ipfs_hashes.append("QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8")
            permanent_ipfs_hashes.append("QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E")

        n0.issueunique("ISSUE_ROOT_ASSET", asset_tags, ipfs_hashes, address0, change_address,
                       permanent_ipfs_hashes, toll_address, toll_amount)


        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        for i in range(0, 10):
            self.log.info("Checkout getassetdata()...")
            assetdata = n0.getassetdata(f"ISSUE_ROOT_ASSET#TAG{i+1}")
            assert_equal(assetdata["name"], f"ISSUE_ROOT_ASSET#TAG{i+1}")
            assert_equal(assetdata["amount"], 1)
            assert_equal(assetdata["units"], 0)
            assert_equal(assetdata["reissuable"], 0)
            assert_equal(assetdata["has_ipfs"], 1)
            assert_equal(assetdata["ipfs_hash"], ipfs_hashes[i])
            assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hashes[i])
            assert_equal(assetdata["toll_amount_mutability"], 1)
            assert_equal(assetdata["toll_amount"], 1)
            assert_equal(assetdata["toll_address_mutability"], 1)
            assert_equal(assetdata["toll_address"], toll_address)

        address2 = n0.getnewaddress()

        txid = n0.transfer("ISSUE_ROOT_ASSET#TAG1", 1, address2)
        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        vout = n0.decoderawtransaction(n0.gettransaction(txid[0])['hex'])['vout']

        # 1 Unique asset was set, and the toll was set to 1.
        # Verify that 1 EVR was paid as the toll when it was transferred
        verified_toll_paid = False
        for item in vout:
            if item['value'] == 1.00000000 and toll_address in item['scriptPubKey']['addresses']:
                verified_toll_paid = True

        assert verified_toll_paid

    def base_burn_remint(self):
        self.log.info("Running burn remint")
        n0, n1 = self.nodes[0], self.nodes[1]
        BURNMINTADDRESS = "n1BurnMintXXXXXXXXXXXXXXXXXXbVTQiY"

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        n0.issue("BURN_MINT_1", 1000, address0)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("BURN_MINT_1")
        assert_equal(assetdata["name"], "BURN_MINT_1")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 0)
        assert_equal(assetdata["currently_burned"], 0)
        assert_equal(assetdata["reminted_total"], 0)

        transfer_change_address = n0.getnewaddress()
        n0.transfer("BURN_MINT_1", 500, BURNMINTADDRESS, "", 0, transfer_change_address)

        self.log.info("Waiting for ten confirmations after issue...")
        blockhash = n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("BURN_MINT_1")
        assert_equal(assetdata["name"], "BURN_MINT_1")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 0)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 0)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(float(assetdata["toll_amount"]), float(0))
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

        # Invalidate the block that burned the asset, make sure the asset value is unburned.
        n0.invalidateblock(blockhash[0])
        assetdata = n0.getassetdata("BURN_MINT_1")
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 0)
        assert_equal(assetdata["currently_burned"], 0)
        assert_equal(assetdata["reminted_total"], 0)

        # Add the block back to the chain nad make sure the asset value is burned
        n0.reconsiderblock(blockhash[0])
        assetdata = n0.getassetdata("BURN_MINT_1")
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

        addressmint = n0.getnewaddress()
        n0.remint("BURN_MINT_1", 500, addressmint)

        self.log.info("Waiting for ten confirmations after issue...")
        blockhash = n0.generate(1)
        self.sync_all()

        asset_balances = n0.listaddressesbyasset("BURN_MINT_1")
        assert_equal(asset_balances[addressmint], 500)
        assert_equal(asset_balances[transfer_change_address], 500)
        assert_equal(asset_balances[BURNMINTADDRESS], 500)

        assetdata = n0.getassetdata("BURN_MINT_1")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 0)
        assert_equal(assetdata["reminted_total"], 500)

        # Invalidate the block that reminted the asset, make sure the asset remint is removed.
        n0.invalidateblock(blockhash[0])
        assetdata = n0.getassetdata("BURN_MINT_1")
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

        # Reconsider the block that reminted the asset, make sure the asset remint is added.
        n0.reconsiderblock(blockhash[0])
        assetdata = n0.getassetdata("BURN_MINT_1")
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 0)
        assert_equal(assetdata["reminted_total"], 500)

        # Burn so assets before we try to remint, don't mine them.
        # Remint should fail because there isn't enough burned assets to remint
        n0.transfer("BURN_MINT_1", 100, BURNMINTADDRESS, "", 0, transfer_change_address)
        n0.transfer("BURN_MINT_1", 100, BURNMINTADDRESS, "", 0, transfer_change_address)
        assert_raises_rpc_error(-25, "reminting amount is greater than what is currently burned", n0.remint, "BURN_MINT_1", 200, addressmint)

        self.log.info("Waiting for ten confirmations after issue...")
        blockhash = n0.generate(1)
        self.sync_all()

        # Now that the two 100 BURN transactions have been mined
        assetdata = n0.getassetdata("BURN_MINT_1")
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 700)
        assert_equal(assetdata["currently_burned"], 200)
        assert_equal(assetdata["reminted_total"], 500)

        # Try to remint 201
        assert_raises_rpc_error(-25, "reminting amount is greater than what is currently burned", n0.remint, "BURN_MINT_1", 201, addressmint)

        # Remint 200
        n0.remint("BURN_MINT_1", 200, addressmint)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        assetdata = n0.getassetdata("BURN_MINT_1")
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 700)
        assert_equal(assetdata["currently_burned"], 0)
        assert_equal(assetdata["reminted_total"], 700)

    def remint_amount_zero(self):
        self.log.info("Running remint amount zero")
        n0, n1 = self.nodes[0], self.nodes[1]
        BURNMINTADDRESS = "n1BurnMintXXXXXXXXXXXXXXXXXXbVTQiY"

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        n0.issue("MINT_AMOUNT_ZERO", 1000, address0)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("MINT_AMOUNT_ZERO")
        assert_equal(assetdata["name"], "MINT_AMOUNT_ZERO")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 0)
        assert_equal(assetdata["currently_burned"], 0)
        assert_equal(assetdata["reminted_total"], 0)

        transfer_change_address = n0.getnewaddress()
        n0.transfer("MINT_AMOUNT_ZERO", 500, BURNMINTADDRESS, "", 0, transfer_change_address)

        self.log.info("Waiting for ten confirmations after issue...")
        blockhash = n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("MINT_AMOUNT_ZERO")
        assert_equal(assetdata["name"], "MINT_AMOUNT_ZERO")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 0)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 0)
        assert_equal(assetdata["permanent_ipfs_hash"], "")
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(float(assetdata["toll_amount"]), float(0))
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

        addressmint = n0.getnewaddress()
        n0.remint("MINT_AMOUNT_ZERO", 0, addressmint, "")

        self.log.info("Waiting for ten confirmations after issue...")
        blockhash = n0.generate(1)
        self.sync_all()

    def remint_unique_asset(self):
        self.log.info("Running remint unique asset")
        n0, n1 = self.nodes[0], self.nodes[1]
        BURNMINTADDRESS = "n1BurnMintXXXXXXXXXXXXXXXXXXbVTQiY"

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        n0.issue("REMINT_UNIQUE_ASSET_ROOT", 1000, address0)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        asset_tags = []
        ipfs_hashes = []
        permanent_ipfs_hashes = []
        for i in range(0, 10):
            asset_tags.append(f"TAG{i+1}")
            ipfs_hashes.append("QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8")
            permanent_ipfs_hashes.append("QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E")

        n0.issueunique("REMINT_UNIQUE_ASSET_ROOT", asset_tags, ipfs_hashes, address0, n0.getnewaddress(),
                       permanent_ipfs_hashes)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REMINT_UNIQUE_ASSET_ROOT")
        assert_equal(assetdata["name"], "REMINT_UNIQUE_ASSET_ROOT")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 0)
        assert_equal(assetdata["currently_burned"], 0)
        assert_equal(assetdata["reminted_total"], 0)

        transfer_change_address = n0.getnewaddress()
        n0.transfer("REMINT_UNIQUE_ASSET_ROOT#TAG1", 1, BURNMINTADDRESS, "", 0, transfer_change_address)

        self.log.info("Waiting for ten confirmations after issue...")
        blockhash = n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REMINT_UNIQUE_ASSET_ROOT#TAG1")
        assert_equal(assetdata["name"], "REMINT_UNIQUE_ASSET_ROOT#TAG1")
        assert_equal(assetdata["amount"], 1)
        assert_equal(assetdata["units"], 0)
        assert_equal(assetdata["reissuable"], 0)
        assert_equal(assetdata["has_ipfs"], 1)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(float(assetdata["toll_amount"]), float(0))
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], "")
        assert_equal(assetdata["remintable"], 0)
        assert_equal(assetdata["burned_total"], 1)
        assert_equal(assetdata["currently_burned"], 1)
        assert_equal(assetdata["reminted_total"], 0)

        addressmint = n0.getnewaddress()
        assert_raises_rpc_error(-25, "reminting_asset flag must be false if asset in not remintable", n0.remint,"REMINT_UNIQUE_ASSET_ROOT#TAG1", 1, addressmint, "")

    def reissue_unique_asset(self):
        self.log.info("Running reissue unique asset")
        n0, n1 = self.nodes[0], self.nodes[1]
        BURNMINTADDRESS = "n1BurnMintXXXXXXXXXXXXXXXXXXbVTQiY"

        self.log.info("Calling issue()...")
        address0 = n0.getnewaddress()
        n0.issue("REISSUE_ASSET_ROOT", 1000, address0)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        asset_tags = []
        ipfs_hashes = []
        permanent_ipfs_hashes = []
        for i in range(0, 10):
            asset_tags.append(f"TAG{i+1}")
            ipfs_hashes.append("QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8")
            permanent_ipfs_hashes.append("QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E")

        n0.issueunique("REISSUE_ASSET_ROOT", asset_tags, ipfs_hashes, address0, n0.getnewaddress(),
                       permanent_ipfs_hashes, address0, 1)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("REISSUE_ASSET_ROOT")
        assert_equal(assetdata["name"], "REISSUE_ASSET_ROOT")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 0)
        assert_equal(assetdata["currently_burned"], 0)
        assert_equal(assetdata["reminted_total"], 0)

        for i in range(0, 10):
            self.log.info("Checkout getassetdata()...")
            assetdata = n0.getassetdata(f"REISSUE_ASSET_ROOT#TAG{i+1}")
            assert_equal(assetdata["name"], f"REISSUE_ASSET_ROOT#TAG{i+1}")
            assert_equal(assetdata["amount"], 1)
            assert_equal(assetdata["units"], 0)
            assert_equal(assetdata["reissuable"], 0)
            assert_equal(assetdata["has_ipfs"], 1)
            assert_equal(assetdata["ipfs_hash"], ipfs_hashes[i])
            assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hashes[i])
            assert_equal(assetdata["toll_amount_mutability"], 1)
            assert_equal(assetdata["toll_amount"], 1)
            assert_equal(assetdata["toll_address_mutability"], 1)
            assert_equal(assetdata["toll_address"], address0)

        for i in range(0, 10):
            n0.reissue(f"REISSUE_ASSET_ROOT#TAG{i+1}", 0, address0, "", False, -1, "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7E", "", True, 0.5, "", True, False)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        for i in range(0, 10):
            self.log.info("Checkout getassetdata()...")
            assetdata = n0.getassetdata(f"REISSUE_ASSET_ROOT#TAG{i+1}")
            assert_equal(assetdata["name"], f"REISSUE_ASSET_ROOT#TAG{i+1}")
            assert_equal(assetdata["amount"], 1)
            assert_equal(assetdata["units"], 0)
            assert_equal(assetdata["reissuable"], 0)
            assert_equal(assetdata["has_ipfs"], 1)
            assert_equal(assetdata["ipfs_hash"], permanent_ipfs_hashes[i])
            assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hashes[i])
            assert_equal(assetdata["toll_amount_mutability"], 1)
            assert_equal(assetdata["toll_amount"], 0.5)
            assert_equal(assetdata["toll_address_mutability"], 0)
            assert_equal(assetdata["toll_address"], address0)

        new_toll_address = n1.getnewaddress()
        for i in range(0, 10):
            n0.updatemetadata(f"REISSUE_ASSET_ROOT#TAG{i+1}", "", "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV99", "", new_toll_address, True, 0.25, True, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        for i in range(0, 10):
            self.log.info("Checkout getassetdata()...")
            assetdata = n0.getassetdata(f"REISSUE_ASSET_ROOT#TAG{i+1}")
            assert_equal(assetdata["name"], f"REISSUE_ASSET_ROOT#TAG{i+1}")
            assert_equal(assetdata["amount"], 1)
            assert_equal(assetdata["units"], 0)
            assert_equal(assetdata["reissuable"], 0)
            assert_equal(assetdata["has_ipfs"], 1)
            assert_equal(assetdata["ipfs_hash"], "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV99")
            assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hashes[i])
            assert_equal(assetdata["toll_amount_mutability"], 1)
            assert_equal(assetdata["toll_amount"], 0.25)
            assert_equal(assetdata["toll_address_mutability"], 0)
            assert_equal(assetdata["toll_address"], address0)

        for i in range(0, 10):
            n0.updatemetadata(f"REISSUE_ASSET_ROOT#TAG{i+1}", "", "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV65", "", "", True, 0.10, False, True)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        for i in range(0, 10):
            self.log.info("Checkout getassetdata()...")
            assetdata = n0.getassetdata(f"REISSUE_ASSET_ROOT#TAG{i+1}")
            assert_equal(assetdata["name"], f"REISSUE_ASSET_ROOT#TAG{i+1}")
            assert_equal(assetdata["amount"], 1)
            assert_equal(assetdata["units"], 0)
            assert_equal(assetdata["reissuable"], 0)
            assert_equal(assetdata["has_ipfs"], 1)
            assert_equal(assetdata["ipfs_hash"], "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV65")
            assert_equal(assetdata["permanent_ipfs_hash"], permanent_ipfs_hashes[i])
            assert_equal(assetdata["toll_amount_mutability"], 0)
            assert_equal(float(assetdata["toll_amount"]), float(0.1000000))
            assert_equal(assetdata["toll_address_mutability"], 0)
            assert_equal(assetdata["toll_address"], address0)

    def reissue_legacy_unique_asset(self):
        self.log.info("Running reissue legacy unique asset")
        n0, n1 = self.nodes[0], self.nodes[1]
        address0 = n0.getnewaddress()

        for i in range(0, 10):
            n0.reissue(f"LEGACY_ASSET_FOR_TOLLS#TAG{i+1}", 0, address0, "", False, -1, "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7Z", "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7Q", True, 0.5, "", True, False)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        for i in range(0, 10):
            self.log.info("Checkout getassetdata()...")
            assetdata = n0.getassetdata(f"LEGACY_ASSET_FOR_TOLLS#TAG{i+1}")
            assert_equal(assetdata["name"], f"LEGACY_ASSET_FOR_TOLLS#TAG{i+1}")
            assert_equal(assetdata["amount"], 1)
            assert_equal(assetdata["units"], 0)
            assert_equal(assetdata["reissuable"], 0)
            assert_equal(assetdata["has_ipfs"], 1)
            assert_equal(assetdata["ipfs_hash"], "QmTqu3Lk3gmTsQVtjU7rYYM37EAW4xNmbuEAp2Mjr4AV7Z")
            assert_equal(assetdata["permanent_ipfs_hash"], "QmcvyefkqQX3PpjpY5L8B2yMd47XrVwAipr6cxUt2zvYU8")
            assert_equal(assetdata["toll_amount_mutability"], 0)
            assert_equal(assetdata["toll_amount"], 0)
            assert_equal(assetdata["toll_address_mutability"], 0)

    def remint_legacy_asset_that_got_burned_remintable(self):
        self.log.info("Running remint_legacy_asset_that_got_burned_remintable")
        n0, n1 = self.nodes[0], self.nodes[1]

        # Legacy asset was V1 reissuable, got burned, became V2
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_2")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS_2")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

        addressmint = n0.getnewaddress()
        n0.remint("LEGACY_ASSET_FOR_TOLLS_2", 250, addressmint)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        asset_balances = n0.listaddressesbyasset("LEGACY_ASSET_FOR_TOLLS_2")
        assert_equal(asset_balances[addressmint], 250)

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 250)
        assert_equal(assetdata["reminted_total"], 250)

    def remint_legacy_asset_that_got_burned_non_remintable(self):
        self.log.info("Running remint_legacy_asset_that_got_burned_non_remintable")
        n0, n1 = self.nodes[0], self.nodes[1]

        # Legacy asset was V1 not reissuable, got burned, became V2
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_4")
        assert_equal(assetdata["name"], "LEGACY_ASSET_FOR_TOLLS_4")
        assert_equal(assetdata["version"], "2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["remintable"], 0)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

        addressmint = n0.getnewaddress()
        assert_raises_rpc_error(-25, "Unable to remint asset: remintable set to false", n0.remint, "LEGACY_ASSET_FOR_TOLLS_4", 250, addressmint)

        self.log.info("Waiting for ten confirmations after issue...")
        n0.generate(1)
        self.sync_all()

        assetdata = n0.getassetdata("LEGACY_ASSET_FOR_TOLLS_2")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 250)
        assert_equal(assetdata["reminted_total"], 250)

    def isvalid_verifier_string(self):
        self.log.info("Testing isvalidverifierstring()...")
        n0 = self.nodes[0]

        n0.issuequalifierasset("#KYC1")
        n0.issuequalifierasset("#KYC2")
        n0.issuequalifierasset("#KYC3")
        n0.issuequalifierasset("#KYC4")
        n0.issuequalifierasset("#KYC5")
        n0.issuequalifierasset("#KYC6")
        n0.issuequalifierasset("#KYC7")
        n0.issuequalifierasset("#KYC8")
        n0.issuequalifierasset("#KYC9")
        n0.issuequalifierasset("#KYC10")
        n0.issuequalifierasset("#KYC11")
        n0.issuequalifierasset("#KYC12")
        n0.issuequalifierasset("#KYC13")
        n0.issuequalifierasset("#KYC14")
        n0.issuequalifierasset("#KYC15")

        n0.generate(1)

        valid = [
            "true",
            "#KYC1",
            "#KYC2",
            "#KYC1 & #KYC2",
            "#KYC1 & #KYC2 & #KYC3 & #KYC4 & #KYC5 & #KYC6 & #KYC7 & #KYC8 & #KYC9 & #KYC10 & #KYC11 & #KYC12 & #KYC13 & #KYC14 & #KYC15"
        ]
        for s in valid:
            assert_equal("Valid Verifier", n0.isvalidverifierstring(s))

        invalid_empty = [
            "",
            "    "
        ]
        for s in invalid_empty:
            assert_raises_rpc_error(-8, "Verifier string can not be empty", n0.isvalidverifierstring, s)

        invalid_syntax = [
            "asdf",
            "#KYC1 - #KYC2"
        ]
        for s in invalid_syntax:
            assert_raises_rpc_error(-8, "failed-syntax", n0.isvalidverifierstring, s)

        invalid_non_issued = ["#NOPE"]
        for s in invalid_non_issued:
            assert_raises_rpc_error(-8, "contains-non-issued-qualifier", n0.isvalidverifierstring, s)

        address = n0.getnewaddress()
        asset_name = "LENGTH_TEST"
        asset_name_2 = "LENGTH_TEST2"
        n0.issue(asset_name, 1000, address)
        n0.issue(asset_name_2, 1000, address)
        n0.generate(1)

        n0.addtagtoaddress("#KYC1", address)
        n0.addtagtoaddress("#KYC2", address)
        n0.addtagtoaddress("#KYC3", address)
        n0.addtagtoaddress("#KYC4", address)
        n0.addtagtoaddress("#KYC5", address)
        n0.addtagtoaddress("#KYC6", address)
        n0.addtagtoaddress("#KYC7", address)
        n0.addtagtoaddress("#KYC8", address)
        n0.addtagtoaddress("#KYC9", address)
        n0.addtagtoaddress("#KYC10", address)
        n0.addtagtoaddress("#KYC11", address)
        n0.addtagtoaddress("#KYC12", address)
        n0.addtagtoaddress("#KYC13", address)
        n0.addtagtoaddress("#KYC14", address)
        n0.addtagtoaddress("#KYC15", address)

        n0.generate(1)

        # This comes out to be 80 character once whitespace and # are removed
        verifier = "#KYC1 & #KYC2 & #KYC3 & #KYC4 & #KYC5 & #KYC6 & #KYC7 & #KYC8 & #KYC9 & #KYC10 & #KYC11 & #KYC12 & #KYC13 & #KYC14 & #KYC15"
        n0.issuerestrictedasset(f"${asset_name}", 1000, verifier, address)
        n0.generate(1)

        verifier_small = "#KYC1 & #KYC2 & #KYC3 & #KYC4 & #KYC5 & #KYC6 & #KYC7"
        n0.issuerestrictedasset(f"${asset_name_2}", 1000, verifier_small, address)
        n0.generate(1)

        assert_equal("KYC1&KYC2&KYC3&KYC4&KYC5&KYC6&KYC7", n0.getverifierstring(f"${asset_name_2}"))
        assert_equal("KYC1&KYC2&KYC3&KYC4&KYC5&KYC6&KYC7&KYC8&KYC9&KYC10&KYC11&KYC12&KYC13&KYC14&KYC15", n0.getverifierstring(f"${asset_name}"))

    def remint_burn_toll_restricted_assets(self):
        self.log.info("Testing remint_burn_restricted_assets()...")
        n0 = self.nodes[0]
        n1 = self.nodes[1]

        # Create the tags/qualifiers
        n0.issuequalifierasset("#TESTBURNKYC1")
        n0.issuequalifierasset("#TESTMINTKYC1")

        n0.generate(1)

        assert_equal("Valid Verifier", n0.isvalidverifierstring("#TESTBURNKYC1"))
        assert_equal("Valid Verifier", n0.isvalidverifierstring("#TESTMINTKYC1"))

        # Issue the root asset
        address = n0.getnewaddress()
        asset_name = "REMINT_ROOT_ASSET"
        n0.issue(asset_name, 1000, address)
        n0.generate(1)

        # Tag / Qualifier that address we want to issue the restricted asset to.
        n0.addtagtoaddress("#TESTBURNKYC1", address)
        n0.addtagtoaddress("#TESTMINTKYC1", address)

        n0.generate(1)

        # Issue the restricted asset
        tolladdress = n1.getnewaddress()
        verifier = "#TESTBURNKYC1 | #TESTMINTKYC1"
        n0.issuerestrictedasset(f"${asset_name}", 1000, verifier, address, "", 0, True, False, "", "", 0.005, tolladdress, True, True)
        n0.generate(1)

        # Verify the restricted asset was issues with the correct verifier
        assert_equal("TESTBURNKYC1|TESTMINTKYC1", n0.getverifierstring(f"${asset_name}"))

        # Try to transfer 500 of the restrited asset to the BURN MINT Address - Failing because it is not verified
        BURNMINTADDRESS = "n1BurnMintXXXXXXXXXXXXXXXXXXbVTQiY"
        assert_raises_rpc_error(-8, "bad-txns-null-verifier-address-failed-verification",n0.transfer, f"${asset_name}", 500, BURNMINTADDRESS)

        # Tag / Qualify the BURN MINT Address
        n0.addtagtoaddress("TESTBURNKYC1", BURNMINTADDRESS)

        n0.generate(1)
        self.sync_all()

        assert_contains_key("#TESTBURNKYC1",n0.listtagsforaddress(BURNMINTADDRESS))

        # Transfer the restricted asset to the burn mint address now that it is qualified
        # The toll should be paid by the wallet. Uncomment that assert False if you need to check the details
        BURNMINTADDRESS = "n1BurnMintXXXXXXXXXXXXXXXXXXbVTQiY"
        n0.transfer(f"${asset_name}", 500, BURNMINTADDRESS)

        n0.generate(1)
        self.sync_all()

        # Uncomment to test toll adjustments in the logs
        # assert(False)

        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata(f"${asset_name}")
        assert_equal(assetdata["name"], f"${asset_name}")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 0)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 0)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(float(assetdata["toll_amount"]), float(0.005))
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], tolladdress)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 500)
        assert_equal(assetdata["reminted_total"], 0)

        remintaddress = n0.getnewaddress()
        # Try and fail to remint to an address that hasn't been qualified
        assert_raises_rpc_error(-8, "bad-txns-null-verifier-address-failed-verification",n0.remint, f"${asset_name}", 250, remintaddress)

        # Tag the address we are trying to remint to
        n0.addtagtoaddress("TESTMINTKYC1", remintaddress)

        n0.generate(1)
        self.sync_all()

        # Remint the restricted asset
        n0.remint(f"${asset_name}", 250, remintaddress)

        n0.generate(1)
        self.sync_all()

        # Verify the remint was tracked corrected
        self.log.info("Checkout getassetdata()...")
        assetdata = n0.getassetdata(f"${asset_name}")
        assert_equal(assetdata["name"], f"${asset_name}")
        assert_equal(assetdata["amount"], 1000)
        assert_equal(assetdata["units"], 0)
        assert_equal(assetdata["reissuable"], 1)
        assert_equal(assetdata["has_ipfs"], 0)
        assert_equal(assetdata["toll_amount_mutability"], 1)
        assert_equal(float(assetdata["toll_amount"]), float(0.005))
        assert_equal(assetdata["toll_address_mutability"], 1)
        assert_equal(assetdata["toll_address"], tolladdress)
        assert_equal(assetdata["remintable"], 1)
        assert_equal(assetdata["burned_total"], 500)
        assert_equal(assetdata["currently_burned"], 250)
        assert_equal(assetdata["reminted_total"], 250)

        # Remove the tag/qualifier from the remint address and try to remint again
        n0.removetagfromaddress("TESTMINTKYC1", remintaddress)

        n0.generate(1)
        self.sync_all()

        # Try and fail to remint to an address that hasn't been qualified
        assert_raises_rpc_error(-8, "bad-txns-null-verifier-address-failed-verification",n0.remint, f"${asset_name}", 250, remintaddress)

    ### TODO's
    ### restricted asset testing with tolls - requires updating issuerestrictedasset rpc
    ###

    def run_test(self):
        # Setup Tests
        self.issue_legacy_assets()
        self.activate_tolls()

        # Legacy Asset Tests
        self.reissue_legacy_asset_v1_reissuable_true_check_remintable_value()
        self.reissue_legacy_asset_v1_reissuable_false_check_remintable_value()
        self.burn_legacy_asset_v1_reissuable_true_check_remintable()
        self.burn_legacy_asset_v1_reissuable_false_check_remintable()
        self.remint_legacy_asset_that_got_burned_remintable()
        self.remint_legacy_asset_that_got_burned_non_remintable()
        self.reissue_legacy_unique_asset()

        # Burn Remint Test
        self.base_burn_remint()
        self.remint_amount_zero()
        self.remint_unique_asset()

        # Version Upgrading Tests - Permanent IPFS Tests
        self.issue_reissue_v1_v2_version_checks()
        self.issue_reissue_permanent_ipfs_mutability_when_reissue_true()
        self.issue_reissue_permanent_ipfs_mutability_when_reissue_false()
        self.issue_ipfs_non_reissuable_permanent_ipfshash()

        # Issue / Transfer Assets with Tolls Tests
        self.issue_asset_with_toll_info()
        self.issue_asset_with_invalid_toll_data()
        self.issue_unique_asset_with_toll_info_and_transfer()
        self.transfer_toll_asset()
        self.transfer_toll_asset_to_burn_address()
        self.transfer_toll_asset_two_nodes()
        self.toll_transfer_custom_transactions()

        # Calculate Tolls Tests
        self.calculate_tolls()

        # Reissue Tests
        self.reissue_permanent_ipfs_hash()
        self.reissue_ipfs_hash_all_flags_false()
        self.reissue_fails_with_no_changes()
        self.reissue_invalid_unit_with_valid_toll_address_change()
        self.reissue_invalid_amount_with_valid_toll_address_change()
        self.reissue_invalid_ipfs_with_valid_toll_address_change()
        self.reissue_toll_assets_big_test()
        self.reissue_toll_amount()
        self.reissue_toll_address()
        self.remint_burn_fee_check()
        self.reissue_burn_amount_check_1()
        self.reissue_burn_amount_check_100()

        # Updatemetadata RPC Tests
        self.updatemetadata_all()
        self.updatemetadata_ipfs_only()
        self.updatemetadata_permanent_ipfs_hash_already_set()
        self.updatemetadata_permanent_ipfs_hash_not_set()
        self.updatemetadata_change_toll_address()
        self.updatemetadata_change_toll_address_mutability_off()
        self.updatemetadata_change_toll_amount()
        self.updatemetadata_change_toll_amount_mutability_off()

        # Restricted Assets Tests
        self.isvalid_verifier_string()
        self.remint_burn_toll_restricted_assets()

        # Unique Assets Tests
        self.reissue_unique_asset()

if __name__ == '__main__':
    TollBurnTest().main()
