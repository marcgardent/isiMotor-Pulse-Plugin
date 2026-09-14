=== udp-bench summary (ran 60.2s) ===
Port   Type Name                   Frames Datagrams    Hz(avg)    Jit-min   Jit-mean    Jit-max  Jit-rfc3550(ms)           Loss
5001   1    TelemInfo                 481       961       8.00     80.604    124.998    180.810            1.639          0 ( 0.00%)
5002   2    CompactScoring            300       300       4.98    121.021    200.663    330.381          102.664          0 ( 0.00%)
5003   3    SystemEvent                 0         0       0.00      0.000      0.000      0.000            0.000          0 ( 0.00%)
5004   4    FullScoringSession        181      1261       3.00    248.133    333.324    418.630           80.496          0 ( 0.00%)
5007   7    WeatherControl              0         0       0.00      0.000      0.000      0.000            0.000          0 ( 0.00%)
5008   8    ExtendedState             240       240       4.00    203.667    249.995    276.935            0.489          0 ( 0.00%)
5009   9    ForceFeedback             482       482       8.00     81.761    124.997    173.574            1.379          0 ( 0.00%)
5010   10   Graphics                    0         0       0.00      0.000      0.000      0.000            0.000          0 ( 0.00%)


zmq-bench: subscribing to 8 port(s) on 127.0.0.1 (base_port=5000), running for 60s

Port   Type Name                   Frames    Hz(avg)    Jit-min   Jit-mean    Jit-max  Jit-rfc3550(ms)   Stalls
5001   1    TelemInfo                 480       8.00     59.770    124.995    173.434            1.802        0
5002   2    CompactScoring            300       5.00    119.507    199.832    292.968          101.296        0
5003   3    SystemEvent                 0       0.00      0.000      0.000      0.000            0.000        0
5004   4    FullScoringSession        180       3.00    236.901    333.089    388.133           85.439        0
5007   7    Weather                     0       0.00      0.000      0.000      0.000            0.000        0
5008   8    ExtendedState             239       3.99    243.740    250.516    308.583            1.176        0
5009   9    ForceFeedback             480       8.00     59.089    124.998    168.139            0.723        0
5010   10   Graphics                    0       0.00      0.000      0.000      0.000            0.000        0
