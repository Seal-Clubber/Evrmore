// Copyright (c) 2017 The Bitcoin Core developers
// Copyright (c) 2017-2020 The Raven Core developers
// Copyright (c) 2022 The Evrmore Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef EVRMORE_RPC_ASSETS_H
#define EVRMORE_RPC_ASSETS_H

#include <string>
#include "amount.h"

class UniValue;
class CNewAsset;
class JSONRPCRequest;

void CheckRestrictedAssetTransferInputs(const CWalletTx& transaction, const std::string& asset_name);

/** Warning helpers */
std::string AssetActivationWarning();
std::string RestrictedActivationWarning();
std::string AssetTypeToString(AssetType& assetType);

/** Restricted Assets functions */
UniValue UpdateAddressTag(const JSONRPCRequest &request, const int8_t &flag);
UniValue UpdateAddressRestriction(const JSONRPCRequest &request, const int8_t &flag);
UniValue UpdateGlobalRestrictedAsset(const JSONRPCRequest &request, const int8_t &flag);

/** Asset data to UniValue helper methods */
void assetToJSON(const CNewAsset& asset, UniValue& result);
void AddBaseAssetInfoToUniValue(const CNewAsset& asset, UniValue& result);
void AddIpfsInfoToUniValue(const CNewAsset& asset, UniValue& result);
void AddTollAssetInfoToUniValue(const CNewAsset& asset, UniValue& result);
UniValue UnitValueFromAmount(const CAmount& amount, const std::string asset_name);


#endif

