export default function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'POST만 지원해.' });
  }
  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    const months = Number(body?.termMonths);
    if (!Number.isInteger(months) || months < 1 || months > 120) throw Error('기간은 1~120개월로 입력해줘.');
    if (!Array.isArray(body?.offers) || body.offers.length < 2 || body.offers.length > 20) throw Error('견적은 2~20개 입력해줘.');
    const integer = (v, label) => {
      const n = Number(v);
      if (!Number.isSafeInteger(n) || n < 0 || n > 1000000000) throw Error(label + '은 0원 이상의 정수로 입력해줘.');
      return n;
    };
    const offers = body.offers.map((x, i) => {
      const provider = String(x.provider || '').trim().slice(0, 80);
      const product = String(x.product || '').trim().slice(0, 40);
      if (!provider || !product) throw Error((i + 1) + '번째 견적의 금융사와 방식을 적어줘.');
      const monthly = integer(x.monthly, '월 납입금');
      const upfront = integer(x.upfront || 0, '초기 비용');
      const deposit = integer(x.deposit || 0, '반환 보증금');
      const buyout = integer(x.buyout || 0, '만기 인수금');
      return { provider, product, monthly, upfront, deposit, buyout,
        returnTotal: upfront + monthly * months,
        buyoutTotal: upfront + monthly * months + buyout };
    });
    res.status(200).json({ vehicle: String(body.vehicle || '').trim().slice(0, 120), termMonths: months, offers,
      lowestMonthlyIndex: offers.reduce((best, x, i) => x.monthly < offers[best].monthly ? i : best, 0),
      lowestReturnIndex: offers.reduce((best, x, i) => x.returnTotal < offers[best].returnTotal ? i : best, 0),
      lowestBuyoutIndex: offers.reduce((best, x, i) => x.buyoutTotal < offers[best].buyoutTotal ? i : best, 0)
    });
  } catch (e) { res.status(400).json({ error: e.message || '입력을 확인해줘.' }); }
}

