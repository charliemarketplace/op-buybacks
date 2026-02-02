from uniswap import sqrtpx96_to_price

"""
    BLOCK_TIMESTAMP,BLOCK_NUMBER,TX_HASH,EVENT_INDEX,SENDER,RECIPIENT,AMOUNT0_RAW,AMOUNT1_RAW,SQRTPRICEX96,LIQUIDITY,TICK
    2026-01-01 00:18:01.000,145813952,0x677b12c1305f675506993fc843f7eeffc91eadfe09fa763b1ad6efa384603fa1,135,0x1ef354f86058c1f4af8b8b1f3ff0c2fc31d539e9,0x51c72848c68a965f66fa7a88855f9f7784502a7f,36292100192146040,-401083331693251421074,8340041809950568377873650817750,11024841948021333274061,93134
"""



# price BEFORE the swap (sqrtpx96 of swap log before our swap above )
print(sqrtpx96_to_price(8342924127496250623015486190045, invert=False, decimal_adjustment=1))

# average execution price, here OP/ETH after adjusting for ETH fees 
print( 401083331693251421074 / (36292100192146040 * 0.997) )

# price AFTER the swap (sqrtpx96 of swap log above, the log returns the post-swap price )
print(sqrtpx96_to_price(8340041809950568377873650817750, invert=False, decimal_adjustment=1))
