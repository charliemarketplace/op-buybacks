-- Daily OP Mainnet transaction fees in ETH for January 2026
-- SOURCE: Dune Analytics
SELECT 
    block_date,
    SUM(tx_fee) AS fees_eth
FROM gas.fees 
WHERE blockchain = 'optimism'
    AND block_date >= date '2026-01-01'
    AND block_date < date '2026-02-01'
    AND currency_symbol = 'ETH'
GROUP BY block_date
ORDER BY block_date ASC
