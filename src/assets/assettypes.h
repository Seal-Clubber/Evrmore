// Copyright (c) 2019 The Raven Core developers
// Copyright (c) 2022 The Evrmore Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef EVRMORECOIN_NEWASSET_H
#define EVRMORECOIN_NEWASSET_H

#include <string>
#include <sstream>
#include <list>
#include <unordered_map>
#include "amount.h"
#include "script/standard.h"
#include "primitives/transaction.h"
#include <iostream>
#include <regex>

#define MAX_UNIT 8
#define MIN_UNIT 0

const uint32_t STANDARD_VERSION = 0xABCDEF00;
const uint32_t TOLL_UPGRADE_VERSION = 0xABCDEF01; // Magic number followed by 01, use 02, 03, etc for future upgrades
const std::regex UNIQUE_INDICATOR_REGEX(R"(^[^^~#!]+#[^~#!\/]+$)");

class CAssetsCache;

enum class AssetType
{
    ROOT = 0,
    SUB = 1,
    UNIQUE = 2,
    MSGCHANNEL = 3,
    QUALIFIER = 4,
    SUB_QUALIFIER = 5,
    RESTRICTED = 6,
    VOTE = 7,
    REISSUE = 8,
    REISSUE_METADATA = 9,
    REMINTING = 10,
    OWNER = 11,
    NULL_ADD_QUALIFIER = 12,
    INVALID = 13
};

enum class QualifierType
{
    REMOVE_QUALIFIER = 0,
    ADD_QUALIFIER = 1
};

enum class RestrictedType
{
    UNFREEZE_ADDRESS = 0,
    FREEZE_ADDRESS= 1,
    GLOBAL_UNFREEZE = 2,
    GLOBAL_FREEZE = 3
};

int IntFromAssetType(AssetType type);
AssetType AssetTypeFromInt(int nType);

const char IPFS_SHA2_256 = 0x12;
const char TXID_NOTIFIER = 0x54;
const char IPFS_SHA2_256_LEN = 0x20;

template <typename Stream, typename Operation>
bool ReadWriteAssetHashOriginal(Stream &s, Operation ser_action, std::string &strIPFSHash)
{
    // assuming 34-byte IPFS SHA2-256 decoded hash (0x12, 0x20, 32 more bytes)
    if (ser_action.ForRead())
    {
        strIPFSHash = "";
        if (!s.empty() and s.size() >= 33) {
            char _sha2_256;
            ::Unserialize(s, _sha2_256);
            std::basic_string<char> hash;
            ::Unserialize(s, hash);

            std::ostringstream os;

            // If it is an ipfs hash, we put the Q and the m 'Qm' at the front
            if (_sha2_256 == IPFS_SHA2_256)
                os << IPFS_SHA2_256 << IPFS_SHA2_256_LEN;

            os << hash.substr(0, 32); // Get the 32 bytes of data
            strIPFSHash = os.str();
            return true;
        }
    }
    else
    {
        if (strIPFSHash.length() == 34) {
            ::Serialize(s, IPFS_SHA2_256);
            ::Serialize(s, strIPFSHash.substr(2));
            return true;
        } else if (strIPFSHash.length() == 32) {
            ::Serialize(s, TXID_NOTIFIER);
            ::Serialize(s, strIPFSHash);
            return true;
        }
    }
    return false;
};

template <typename Stream, typename Operation>
bool ReadWriteAssetHash(Stream &s, Operation ser_action, std::string &strIPFSHash, uint32_t version)
{
    if (ser_action.ForRead())
    {
        strIPFSHash = "";

        if (!s.empty() && s.size() >= 1) {
            if (version >= TOLL_UPGRADE_VERSION) {
                // New format: Read length prefix
                uint8_t hashLength;
                ::Unserialize(s, hashLength);

                if (hashLength == 0) {
                    return true;  // No hash present
                }

                if (s.size() >= hashLength) {
                    char _sha2_256;
                    ::Unserialize(s, _sha2_256);
                    std::basic_string<char> hash;
                    ::Unserialize(s, hash);

                    std::ostringstream os;

                    if (_sha2_256 == IPFS_SHA2_256) {
                        os << IPFS_SHA2_256 << IPFS_SHA2_256_LEN;
                    }

                    os << hash.substr(0, hashLength - 2);  // Adjust for prefix length
                    strIPFSHash = os.str();
                    return true;
                }
            } else {
                // Old format: No length prefix, directly read hash
                return ReadWriteAssetHashOriginal(s, ser_action, strIPFSHash);
            }
        }
    }
    else
    {
        if (version >= TOLL_UPGRADE_VERSION) {
            // New format: Serialize with length prefix
            uint8_t hashLength = static_cast<uint8_t>(strIPFSHash.length());
            ::Serialize(s, hashLength);

            if (hashLength == 0) {
                return true;  // No hash present
            }

            if (hashLength == 34) {
                ::Serialize(s, IPFS_SHA2_256);
                ::Serialize(s, strIPFSHash.substr(2));
                return true;
            } else if (hashLength == 32) {
                ::Serialize(s, TXID_NOTIFIER);
                ::Serialize(s, strIPFSHash);
                return true;
            }
        } else {
            // Old format: No length prefix, directly read hash
            return ReadWriteAssetHashOriginal(s, ser_action, strIPFSHash);
        }
    }
    return false;
}

class CNewAsset
{

private:
    bool DoesAssetNameMatchUniqueRegex() {
        return std::regex_match(strName, UNIQUE_INDICATOR_REGEX);
    }

public:
    std::string strName;              // MAX 31 Bytes
    CAmount nAmount;                  // 8 Bytes
    int8_t units;                     // 1 Byte
    int8_t nReissuable;               // 1 Byte
    int8_t nHasIPFS;                  // 1 Byte
    std::string strIPFSHash;          // MAX 40 Bytes

    // New Fields
    std::string strPermanentIPFSHash; // MAX 40 Bytes
    CAmount nTollAmount;              // 8 Bytes
    std::string strTollAddress;       // Toll Address, assume this is a MAX 34-byte string
    int8_t nTollAmountMutability;     // 1 Byte
    int8_t nTollAddressMutability;    // 1 Byte
    uint32_t nExpiringTime;           // Expiring Time field
    uint32_t nVersion;                // 4 Bytes

    // Burn Mint Assets Totals
    int8_t nRemintable;               // 1 Byte
    CAmount nTotalBurned;             // 8 Bytes
    CAmount nCurrentlyBurned;         // 8 Bytes

    CNewAsset()
    {
        SetNull();
    }

    CNewAsset(const std::string& strName, const CAmount& nAmount, const int& units, const int& nReissuable, const int& nHasIPFS, const std::string& strIPFSHash, const std::string& strPermanentIPFSHash, const CAmount& nTollAmount, const std::string& strTollAddress, const int& nTollAmountMutability, const int& nTollAddressMutability, const int& nRemintable, const uint32_t& nExpiringTime = 0);
    CNewAsset(const std::string& strName, const CAmount& nAmount, const int& units, const int& nReissuable, const int& nHasIPFS, const std::string& strIPFSHash);
    CNewAsset(const std::string& strName, const CAmount& nAmount);

    // Copy constructor
    CNewAsset(const CNewAsset& asset);

    // Assignment operator
    CNewAsset& operator=(const CNewAsset& asset);

    // Set default values for all fields
    void SetNull()
    {
        strName = "";
        nAmount = 0;
        units = int8_t(MAX_UNIT);
        nReissuable = int8_t(0);
        nHasIPFS = int8_t(0);
        strIPFSHash = "";
        strPermanentIPFSHash = "";
        nTollAmount = 0;
        strTollAddress = "";
        nTollAmountMutability = int8_t(0);
        nTollAddressMutability = int8_t(0);
        nExpiringTime = uint32_t(0);
        nVersion = STANDARD_VERSION;
        nRemintable = int8_t(0);
        nTotalBurned = 0;
        nCurrentlyBurned = 0;
    }

    bool IsNull() const;
    std::string ToString() const;
    bool IsTollVersion() const;

    void ConstructTransaction(CScript& script) const;
    void ConstructOwnerTransaction(CScript& script) const;

    ADD_SERIALIZE_METHODS;

    template <typename Stream, typename Operation>
    inline void SerializationOp(Stream& s, Operation ser_action)
    {
        HandleVersionSerialization(s, ser_action, nVersion);

        READWRITE(strName);
        READWRITE(nAmount);
        READWRITE(units);
        READWRITE(nReissuable);
        READWRITE(nHasIPFS);

        if (nHasIPFS == 1) {
            ReadWriteAssetHash(s, ser_action, strIPFSHash, nVersion);
        }

        // Handle new fields if the version is at or above the toll upgrade version
        if (nVersion >= TOLL_UPGRADE_VERSION) {
            ReadWriteAssetHash(s, ser_action, strPermanentIPFSHash, nVersion);
            READWRITE(nTollAmount);
            READWRITE(strTollAddress);
            READWRITE(nTollAmountMutability);
            READWRITE(nTollAddressMutability);
            READWRITE(nRemintable);

            // Only serialize nExpiringTime if the asset is unique
            if (DoesAssetNameMatchUniqueRegex()) {
                READWRITE(nExpiringTime);  // Only read/write if it's a unique asset
            }

            // We don't want to serialize this data when sending assets on the network
            // So we check to make sure we only serialize this data when it is a disk operation
            if (s.GetType() & SER_DISK) {
                READWRITE(nTotalBurned);
                READWRITE(nCurrentlyBurned);
            }
        }
    }

    template <typename Stream, typename Operation>
    void HandleVersionSerialization(Stream& s, Operation ser_action, uint32_t& nVersion)
    {
        if (ser_action.ForRead()) {
            try {
                unsigned int originalReadPos = s.nreadPos();
                READWRITE(nVersion);

                if (nVersion != TOLL_UPGRADE_VERSION) {
                    s.Rewind(s.nreadPos() - originalReadPos);
                    nVersion = STANDARD_VERSION;
                }
            } catch (const std::exception& e) {
                s.Rewind(s.nreadPos());
                nVersion = STANDARD_VERSION;
            } catch (...) {
                s.Rewind(s.nreadPos());
                nVersion = STANDARD_VERSION;
            }
        } else {
            // Only write the version if it isn't the original
            if (nVersion >= TOLL_UPGRADE_VERSION) {
                READWRITE(nVersion);
            }
        }
    }
};

class AssetComparator
{
public:
    bool operator()(const CNewAsset& s1, const CNewAsset& s2) const
    {
        return s1.strName < s2.strName;
    }
};

class CDatabasedAssetData
{
public:
    CNewAsset asset;
    int nHeight;
    uint256 blockHash;

    CDatabasedAssetData(const CNewAsset& asset, const int& nHeight, const uint256& blockHash);
    CDatabasedAssetData();

    void SetNull()
    {
        asset.SetNull();
        nHeight = -1;
        blockHash = uint256();
    }

    ADD_SERIALIZE_METHODS;

    template <typename Stream, typename Operation>
    inline void SerializationOp(Stream& s, Operation ser_action)
    {
        READWRITE(asset);
        READWRITE(nHeight);
        READWRITE(blockHash);
    }
};

class CAssetTransfer
{
public:
    std::string strName;
    CAmount nAmount;
    std::string message;
    int64_t nExpireTime;

    CAssetTransfer()
    {
        SetNull();
    }

    void SetNull()
    {
        nAmount = 0;
        strName = "";
        message = "";
        nExpireTime = 0;
    }

    ADD_SERIALIZE_METHODS;

    template <typename Stream, typename Operation>
    inline void SerializationOp(Stream& s, Operation ser_action)
    {
        READWRITE(strName);
        READWRITE(nAmount);
        bool validIPFS = ReadWriteAssetHashOriginal(s, ser_action, message);
        if (validIPFS) {
            if (ser_action.ForRead()) {
                if (!s.empty() && s.size() >= sizeof(int64_t)) {
                    ::Unserialize(s, nExpireTime);
                }
            } else {
                if (nExpireTime != 0) {
                    ::Serialize(s, nExpireTime);
                }
            }
        }

    }

    CAssetTransfer(const std::string& strAssetName, const CAmount& nAmount, const std::string& message = "", const int64_t& nExpireTime = 0);
    bool IsValid(std::string& strError) const;
    void ConstructTransaction(CScript& script) const;
    bool ContextualCheckAgainstVerifyString(CAssetsCache *assetCache, const std::string& address, std::string& strError) const;
};

class CReissueAsset
{
private:
    bool DoesAssetNameMatchUniqueRegex() const {
        return std::regex_match(strName, UNIQUE_INDICATOR_REGEX);
    }

public:
    std::string strName;
    CAmount nAmount;
    int8_t nUnits;
    int8_t nReissuable;
    std::string strIPFSHash;

    // New fields
    std::string strPermanentIPFSHash; // MAX 40 Bytes
    int8_t nTollAmountChanged;         // 1 Byte
    CAmount nTollAmount;               // 8 Byte
    std::string strTollAddress;        // Toll Address, MAX 34-byte string
    int8_t nRemintingAsset;            // 1 Byte
    int8_t nTollAmountMutability;      // 1 Byte
    int8_t nTollAddressMutability;     // 1 Byte
    int8_t nRemintable;                // 1 Byte
    uint32_t nVersion;                 // 4 Byte

    CReissueAsset()
    {
        SetNull();
    }

    void SetNull()
    {
        nAmount = 0;
        strName = "";
        nUnits = 0;
        nReissuable = 1;
        strIPFSHash = "";

        // Initialize new fields
        strPermanentIPFSHash = "";
        nTollAmountChanged = int8_t(0);
        nTollAmount = 0;
        strTollAddress = "";
        nRemintingAsset = int8_t(0);
        nTollAmountMutability = 1;
        nTollAddressMutability = 1;
        nRemintable = 1;
        nVersion = STANDARD_VERSION;  // Default to standard version
    }

    ADD_SERIALIZE_METHODS;

    template <typename Stream, typename Operation>
    inline void SerializationOp(Stream& s, Operation ser_action)
    {
        HandleVersionSerialization(s, ser_action, nVersion);

        READWRITE(strName);
        READWRITE(nAmount);
        READWRITE(nUnits);
        READWRITE(nReissuable);

        // Use version to determine if length prefix is present
        ReadWriteAssetHash(s, ser_action, strIPFSHash, nVersion);

        // When adding new fields for tolls and an additional IPFS hash,
        // we encountered an issue with the existing ReadWriteAssetHash function.
        // This function reads the next 33 bytes from the stream if the stream size is > 33,
        // which worked fine with the original implementation.
        //
        // However, when we added a new hash field, a problem arose:
        // if the original IPFS hash (strIPFSHash) was empty ("") but the stream size was still > 33,
        // it would incorrectly read the new strPermanentIPFSHash as the strIPFSHash.
        //
        // To prevent this, we use the nVersion variable to distinguish between old and new versions
        // of the transaction. In the new versions, we also add the length of the hash to make sure
        // the correct data is read.

        if (nVersion >= TOLL_UPGRADE_VERSION) {
            ReadWriteAssetHash(s, ser_action, strPermanentIPFSHash, nVersion);

            // Serialize toll amount fields if indicated by the flag
            READWRITE(nTollAmountChanged);
            if (nTollAmountChanged) {
                READWRITE(nTollAmount);
            }

            // Serialize the toll address last to keep separation
            READWRITE(strTollAddress);

            // If this reissue is performing a reminting
            READWRITE(nRemintingAsset);

            // Serialize the mutability fields
            READWRITE(nTollAmountMutability);
            READWRITE(nTollAddressMutability);
            READWRITE(nRemintable);
        }
    }


    template <typename Stream, typename Operation>
    void HandleVersionSerialization(Stream& s, Operation ser_action, uint32_t& nVersion)
    {
        if (ser_action.ForRead()) {
            try {
                unsigned int originalReadPos = s.nreadPos();
                READWRITE(nVersion);

                if (nVersion != TOLL_UPGRADE_VERSION) {
                    s.Rewind(s.nreadPos() - originalReadPos);
                    nVersion = STANDARD_VERSION;
                }
            } catch (const std::exception& e) {
                s.Rewind(s.nreadPos());
                nVersion = STANDARD_VERSION;
            } catch (...) {
                s.Rewind(s.nreadPos());
                nVersion = STANDARD_VERSION;
            }
        } else {
            if (nVersion >= TOLL_UPGRADE_VERSION) {
                READWRITE(nVersion);
            }
        }
    }


    // Constructor with all parameters
    CReissueAsset(const std::string& strAssetName, const CAmount& nAmount, const int& nUnits, const int& nReissuable,
                  const std::string& strIPFSHash, const std::string& strPermanentIPFSHash, const int& nTollAmountChanged,
                  const CAmount& nTollAmount, const std::string& strTollAddress, const int& nRemintingAsset, const int& nTollAmountMutability, const int& nTollAddressMutability, const int& nRemintable);
    CReissueAsset(const std::string& strAssetName, const CAmount& nAmount, const int& nUnits, const int& nReissuable, const std::string& strIPFSHash);
    CReissueAsset(const std::string& strAssetName, const CAmount& nAmount, const int& nRemintable);


    void ConstructTransaction(CScript& script) const;
    bool IsNull() const;
    bool IsMetaDataOnly() const;
    bool IsRemintOnly() const;
    bool IsTollVersion() const;
    bool IsAssetNameUnique() const {
        return DoesAssetNameMatchUniqueRegex();
    }

    std::string ToString() const;
};


class CNullAssetTxData {
public:
    std::string asset_name;
    int8_t flag; // on/off but could be used to determine multiple options later on

    CNullAssetTxData()
    {
        SetNull();
    }

    void SetNull()
    {
        flag = -1;
        asset_name = "";
    }

    ADD_SERIALIZE_METHODS;

    template <typename Stream, typename Operation>
    inline void SerializationOp(Stream& s, Operation ser_action)
    {
        READWRITE(asset_name);
        READWRITE(flag);
    }

    CNullAssetTxData(const std::string& strAssetname, const int8_t& nFlag);
    bool IsValid(std::string& strError, CAssetsCache& assetCache, bool fForceCheckPrimaryAssetExists) const;
    void ConstructTransaction(CScript& script) const;
    void ConstructGlobalRestrictionTransaction(CScript &script) const;
};

class CNullAssetTxVerifierString {

public:
    std::string verifier_string;

    CNullAssetTxVerifierString()
    {
        SetNull();
    }

    void SetNull()
    {
        verifier_string ="";
    }

    ADD_SERIALIZE_METHODS;

    template <typename Stream, typename Operation>
    inline void SerializationOp(Stream& s, Operation ser_action)
    {
        READWRITE(verifier_string);
    }

    CNullAssetTxVerifierString(const std::string& verifier);
    void ConstructTransaction(CScript& script) const;
};

/** THESE ARE ONLY TO BE USED WHEN ADDING THINGS TO THE CACHE DURING CONNECT AND DISCONNECT BLOCK */
struct CAssetCacheNewAsset
{
    CNewAsset asset;
    std::string address;
    uint256 blockHash;
    int blockHeight;

    CAssetCacheNewAsset(const CNewAsset& asset, const std::string& address, const int& blockHeight, const uint256& blockHash)
    {
        this->asset = asset;
        this->address = address;
        this->blockHash = blockHash;
        this->blockHeight = blockHeight;
    }

    bool operator<(const CAssetCacheNewAsset& rhs) const
    {
        return asset.strName < rhs.asset.strName;
    }
};

struct CAssetCacheReissueAsset
{
    CReissueAsset reissue;
    std::string address;
    COutPoint out;
    uint256 blockHash;
    int blockHeight;


    CAssetCacheReissueAsset(const CReissueAsset& reissue, const std::string& address, const COutPoint& out, const int& blockHeight, const uint256& blockHash)
    {
        this->reissue = reissue;
        this->address = address;
        this->out = out;
        this->blockHash = blockHash;
        this->blockHeight = blockHeight;
    }

    bool operator<(const CAssetCacheReissueAsset& rhs) const
    {
        return out < rhs.out;
    }

};

struct CAssetCacheNewTransfer
{
    CAssetTransfer transfer;
    std::string address;
    COutPoint out;
    uint256 blockHash;
    int blockHeight;

    CAssetCacheNewTransfer(const CAssetTransfer& transfer, const std::string& address, const COutPoint& out)
    {
        this->transfer = transfer;
        this->address = address;
        this->out = out;
        this->blockHash = uint256();
        this->blockHeight = 0;
    }

    CAssetCacheNewTransfer(const CAssetTransfer& transfer, const std::string& address, const COutPoint& out, const uint256& blockHash, const int& blockHeight)
    {
        this->transfer = transfer;
        this->address = address;
        this->out = out;
        this->blockHash = blockHash;
        this->blockHeight = blockHeight;
    }

    bool operator<(const CAssetCacheNewTransfer& rhs ) const
    {
        return out < rhs.out;
    }
};

struct CAssetCacheNewOwner
{
    std::string assetName;
    std::string address;

    CAssetCacheNewOwner(const std::string& assetName, const std::string& address)
    {
        this->assetName = assetName;
        this->address = address;
    }

    bool operator<(const CAssetCacheNewOwner& rhs) const
    {

        return assetName < rhs.assetName;
    }
};

struct CAssetCacheUndoAssetAmount
{
    std::string assetName;
    std::string address;
    CAmount nAmount;

    CAssetCacheUndoAssetAmount(const std::string& assetName, const std::string& address, const CAmount& nAmount)
    {
        this->assetName = assetName;
        this->address = address;
        this->nAmount = nAmount;
    }
};

struct CAssetCacheSpendAsset
{
    std::string assetName;
    std::string address;
    CAmount nAmount;

    CAssetCacheSpendAsset(const std::string& assetName, const std::string& address, const CAmount& nAmount)
    {
        this->assetName = assetName;
        this->address = address;
        this->nAmount = nAmount;
    }
};

struct CAssetCacheQualifierAddress {
    std::string assetName;
    std::string address;
    QualifierType type;

    CAssetCacheQualifierAddress(const std::string &assetName, const std::string &address, const QualifierType &type) {
        this->assetName = assetName;
        this->address = address;
        this->type = type;
    }

    bool operator<(const CAssetCacheQualifierAddress &rhs) const {
        return assetName < rhs.assetName || (assetName == rhs.assetName && address < rhs.address);
    }

    uint256 GetHash();
};

struct CAssetCacheRootQualifierChecker {
    std::string rootAssetName;
    std::string address;

    CAssetCacheRootQualifierChecker(const std::string &assetName, const std::string &address) {
        this->rootAssetName = assetName;
        this->address = address;
    }

    bool operator<(const CAssetCacheRootQualifierChecker &rhs) const {
        return rootAssetName < rhs.rootAssetName || (rootAssetName == rhs.rootAssetName && address < rhs.address);
    }

    uint256 GetHash();
};

struct CAssetCacheRestrictedAddress
{
    std::string assetName;
    std::string address;
    RestrictedType type;

    CAssetCacheRestrictedAddress(const std::string& assetName, const std::string& address, const RestrictedType& type)
    {
        this->assetName = assetName;
        this->address = address;
        this->type = type;
    }

    bool operator<(const CAssetCacheRestrictedAddress& rhs) const
    {
        return assetName < rhs.assetName || (assetName == rhs.assetName && address < rhs.address);
    }

    uint256 GetHash();
};

struct CAssetCacheRestrictedGlobal
{
    std::string assetName;
    RestrictedType type;

    CAssetCacheRestrictedGlobal(const std::string& assetName, const RestrictedType& type)
    {
        this->assetName = assetName;
        this->type = type;
    }

    bool operator<(const CAssetCacheRestrictedGlobal& rhs) const
    {
        return assetName < rhs.assetName;
    }
};

struct CAssetCacheRestrictedVerifiers
{
    std::string assetName;
    std::string verifier;
    bool fUndoingRessiue;

    CAssetCacheRestrictedVerifiers(const std::string& assetName, const std::string& verifier)
    {
        this->assetName = assetName;
        this->verifier = verifier;
        fUndoingRessiue = false;
    }

    bool operator<(const CAssetCacheRestrictedVerifiers& rhs) const
    {
        return assetName < rhs.assetName;
    }
};

struct CAssetTollTracker {
    std::string assetName;
    CAmount nSetTollFee;       // Toll fee per asset spent
    std::string tollAddress;   // Address where the toll is paid
    CAmount nTotalTollSum;       // Total spent for this asset
    CAmount nTotalAssetSpent;       // Total spent for this asset

    CAssetTollTracker(const std::string& name, CAmount tollFee, const std::string& address, CAmount totalTollSum, CAmount totalAssetSpent)
            : assetName(name), nSetTollFee(tollFee), tollAddress(address), nTotalTollSum(totalTollSum), nTotalAssetSpent(totalAssetSpent) {}

    // Default Constructor
    CAssetTollTracker()
            : assetName(""), nSetTollFee(0), tollAddress(""), nTotalTollSum(0), nTotalAssetSpent(0) {}
};

// Least Recently Used Cache
template<typename cache_key_t, typename cache_value_t>
class CLRUCache
{
public:
    typedef typename std::pair<cache_key_t, cache_value_t> key_value_pair_t;
    typedef typename std::list<key_value_pair_t>::iterator list_iterator_t;

    CLRUCache(size_t max_size) : maxSize(max_size)
    {
    }
    CLRUCache()
    {
        SetNull();
    }

    void Put(const cache_key_t& key, const cache_value_t& value)
    {
        auto it = cacheItemsMap.find(key);
        cacheItemsList.push_front(key_value_pair_t(key, value));
        if (it != cacheItemsMap.end())
        {
            cacheItemsList.erase(it->second);
            cacheItemsMap.erase(it);
        }
        cacheItemsMap[key] = cacheItemsList.begin();

        if (cacheItemsMap.size() > maxSize)
        {
            auto last = cacheItemsList.end();
            last--;
            cacheItemsMap.erase(last->first);
            cacheItemsList.pop_back();
        }
    }

    void Erase(const cache_key_t& key)
    {
        auto it = cacheItemsMap.find(key);
        if (it != cacheItemsMap.end())
        {
            cacheItemsList.erase(it->second);
            cacheItemsMap.erase(it);
        }
    }

    const cache_value_t& Get(const cache_key_t& key)
    {
        auto it = cacheItemsMap.find(key);
        if (it == cacheItemsMap.end())
        {
            throw std::range_error("There is no such key in cache");
        }
        else
        {
            cacheItemsList.splice(cacheItemsList.begin(), cacheItemsList, it->second);
            return it->second->second;
        }
    }

    bool Exists(const cache_key_t& key) const
    {
        return cacheItemsMap.find(key) != cacheItemsMap.end();
    }

    size_t Size() const
    {
        return cacheItemsMap.size();
    }


    void Clear()
    {
        cacheItemsMap.clear();
        cacheItemsList.clear();
    }

    void SetNull()
    {
        maxSize = 0;
        Clear();
    }

    size_t MaxSize() const
    {
        return maxSize;
    }


    void SetSize(const size_t size)
    {
        maxSize = size;
    }

   const std::unordered_map<cache_key_t, list_iterator_t>& GetItemsMap()
    {
        return cacheItemsMap;
    };

    const std::list<key_value_pair_t>& GetItemsList()
    {
        return cacheItemsList;
    };


    CLRUCache(const CLRUCache& cache)
    {
        this->cacheItemsList = cache.cacheItemsList;
        this->cacheItemsMap = cache.cacheItemsMap;
        this->maxSize = cache.maxSize;
    }

private:
    std::list<key_value_pair_t> cacheItemsList;
    std::unordered_map<cache_key_t, list_iterator_t> cacheItemsMap;
    size_t maxSize;
};

#endif //EVRMORECOIN_NEWASSET_H
