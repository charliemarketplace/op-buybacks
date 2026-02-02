-- All swap events from OP/WETH 0.3% pool for January 2026
-- SOURCE: Flipside Crypto
SELECT 
    block_timestamp,
    block_number,
    tx_hash,
    event_index,
    -- Decoded Uniswap V3 Swap parameters
    decoded_log:sender::string AS sender,
    decoded_log:recipient::string AS recipient,
    decoded_log:amount0::string AS amount0_raw,
    decoded_log:amount1::string AS amount1_raw,
    decoded_log:sqrtPriceX96::string AS sqrtPriceX96,
    decoded_log:liquidity::string AS liquidity,
    decoded_log:tick::integer AS tick
FROM optimism.core.ez_decoded_event_logs
WHERE contract_address = '0x68f5c0a2de713a54991e01858fd27a3832401849'
    AND event_name = 'Swap'
    AND block_timestamp >= '2026-01-01 00:00:00'
    AND block_timestamp < '2026-02-01 00:00:00'
ORDER BY block_timestamp ASC