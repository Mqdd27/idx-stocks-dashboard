def build_quant_setup(price, atr, support=None, resistance=None, min_rr=1.5, target_rr=2.0, zone_atr=0.25):
    if not atr or atr <= 0 or price <= 0:
        return None
    stop = max(float(support or price - 1.5 * atr), price - 1.5 * atr)
    if stop >= price:
        stop = price - atr
    risk = price - stop
    if risk <= 0:
        return None
    fallback_tp1 = price + min_rr * risk
    tp1 = float(resistance) if resistance and resistance > price and (resistance - price) / risk >= min_rr else fallback_tp1
    tp2 = max(tp1, price + target_rr * risk)
    rr = (tp1 - price) / risk
    if rr < min_rr:
        return None
    return {"entry": price, "low": max(stop, price - zone_atr * atr), "high": price + zone_atr * atr, "stop": stop, "tp1": tp1, "tp2": tp2, "rr": rr}
