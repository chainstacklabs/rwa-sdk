"""Contract address and metadata registry per chain."""

# Chain IDs
ETHEREUM = 1
ARBITRUM = 42161
POLYGON = 137
AVALANCHE = 43114
BASE = 8453

# Ondo Finance
ONDO = {
    ETHEREUM: {
        "tokens": {
            "usdy": {
                "token": "0x96F6eF951840721AdBF46Ac996b59E0235CB985C",
                "oracle": "0xA0219AA5B31e65Bc920B5b6DFb8EdF0988121De0",
                "blocklist": "0xd8c8174691d936E2C80114EC449037b13421B0a8",
            },
            "rusdy": {
                "token": "0xaf37c1167910ebC994e266949387d2c7C326b879",
            },
            "ousg": {
                "token": "0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92",
                "oracle": "0x9Cad45a8BF0Ed41Ff33074449B357C7a1fAb4094",
                "kyc_registry": "0xcf6958D69d535FD03BD6Df3F4fe6CDcd127D97df",
            },
            "rousg": {
                "token": "0x54043c656F0FAd0652D9Ae2603cDF347c5578d00",
            },
        },
        "shared": {},
    },
    ARBITRUM: {
        "tokens": {
            "usdy": {
                "token": "0x35e050d3C0eC2d29D269a8EcEa763a183bDF9A9D",
            },
        },
        "shared": {},
    },
}

# BlackRock BUIDL (Securitize)
SECURITIZE = {
    ETHEREUM: {
        "tokens": {
            "buidl": {
                "token": "0x7712c34205737192402172409a8F7ccef8aA2AEc",
            },
            "buidl_i": {
                "token": "0x6a9DA2D710BB9B700acde7Cb81F10F1fF8C89041",
            },
        },
        "shared": {},
    },
    ARBITRUM: {
        "tokens": {
            "buidl": {
                "token": "0xA6525Ae43eDCd03dC08E775774dCAbd3bb925872",
            },
        },
        "shared": {},
    },
    AVALANCHE: {
        "tokens": {
            "buidl": {
                "token": "0x53FC82f14F009009b440a706e31c9021E1196A2F",
            },
        },
        "shared": {},
    },
    POLYGON: {
        "tokens": {
            "buidl": {
                "token": "0x2893Ef551B6dD69F661Ac00F11D93E5Dc5Dc0e99",
            },
        },
        "shared": {},
    },
}

# Backed Finance
BACKED = {
    ETHEREUM: {
        "tokens": {
            "bib01": {
                "token": "0xCA30c93B02514f86d5C86a6e375E3A330B435Fb5",
                "chainlink_feed": "0x32d1463EB53b73C095625719Afa544D5426354cB",
            },
            "bcspx": {
                "token": "0x1e2c4fb7ede391d116e6b41cd0608260e8801d59",
                "chainlink_feed": None,  # CSPX/USD feed TBD
            },
            "bnvda": {
                "token": "0xa34c5e0abe843e10461e2c9586ea03e55dbcc495",
            },
        },
        "shared": {
            "sanctions_list": "0x40C57923924B5c5c5455c48D93317139ADDaC8fb",
        },
    },
}

# Centrifuge
CENTRIFUGE = {
    ETHEREUM: {
        "tokens": {
            "jtrsy": {
                "token": "0x8c213ee79581ff4984583c6a801e5263418c4b86",
                "pool_id": "281474976710662",
            },
        },
        "shared": {
            "spoke": "0xEC3582fcDc34078a4B7a8c75a5a3AE46f48525aB",
            "vault_registry": "0xd9531AC47928c3386346f82d9A2478960bf2CA7B",
        },
    },
}

# Maple Finance
MAPLE = {
    ETHEREUM: {
        "tokens": {
            "syrup_usdc": {
                "pool": "0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b",
                "pool_manager": "0x7aD5fFa5fdF509E30186F4609c2f6269f4B6158F",
            },
            "syrup_usdt": {
                "pool": "0x356B8d89c1e1239Cbbb9dE4815c39A1474d5BA7D",
            },
        },
        "shared": {
            "globals": "0x34E7014E2Ef62C2F3Cc8c8c25Ac0110E2aA33B00",
            "pool_permission_manager": "0xBe10aDcE8B6E3E02Db384E7FaDA5395DD113D8b3",
        },
    },
}


def get_addresses(protocol: str, chain_id: int = ETHEREUM) -> dict:
    """Get contract addresses for a protocol on a given chain."""
    registries = {
        "ondo": ONDO,
        "securitize": SECURITIZE,
        "backed": BACKED,
        "centrifuge": CENTRIFUGE,
        "maple": MAPLE,
    }
    registry = registries.get(protocol, {})
    return registry.get(chain_id, {})
