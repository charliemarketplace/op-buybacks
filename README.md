# OP Buybacks

A case study on Optimism's token buyback program.

## Background

In January 2026, Optimism governance [approved](https://www.coindesk.com/business/2026/01/28/optimism-governance-approves-op-token-buyback-plan-tied-to-superchain-revenue) a proposal to allocate **50% of net Superchain sequencer revenue** toward recurring OP token buybacks. The measure passed with 84.4% approval and marks Optimism's first formal effort to tie OP token demand directly to network activity.

### Key Details

- **Duration**: 12-month pilot starting February 2026
- **Allocation**: 50% of sequencer revenue → buybacks; 50% → ecosystem funding, grants, and operations
- **Scope**: Revenue from the Superchain — OP Mainnet, Base, Unichain, World Chain, Soneium, Ink, and other OP Stack chains
- **Scale**: Based on the prior year's 5,868 ETH in revenue, roughly 2,700 ETH (~$8M) would flow to buybacks annually
- **Token handling**: Purchased OP held in treasury; future governance will decide on burns, staking incentives, or redistribution

### Strategic Significance

The Superchain currently captures **61% of L2 fee market share** and processes 13% of all crypto transactions. This buyback mechanism transitions OP from a pure governance token to one with value accrual tied to Superchain growth.

---

## Analysis Scope

This case study focuses on:

- **Revenue source**: OP Mainnet transaction fees only (denominated in ETH)
- **Execution venue**: Uniswap V3 OP/WETH 0.3% pool on OP Mainnet

### Contracts

| Contract | Address |
|----------|---------|
| Uniswap V3 OP/WETH Pool (0.3%) | [`0x68f5c0a2de713a54991e01858fd27a3832401849`](https://optimistic.etherscan.io/address/0x68f5c0a2de713a54991e01858fd27a3832401849) |
| OP Token | [`0x4200000000000000000000000000000000000042`](https://optimistic.etherscan.io/address/0x4200000000000000000000000000000000000042) |
| WETH | [`0x4200000000000000000000000000000000000006`](https://optimistic.etherscan.io/address/0x4200000000000000000000000000000000000006) |

### Notes

- V3 concentrated liquidity requires consideration of position ranges and rebalancing
- For simplicity, analysis may assume wide/full-range positions where applicable
