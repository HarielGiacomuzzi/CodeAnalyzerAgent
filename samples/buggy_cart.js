function cartTotal(items) {
  let total = 0;
  for (let i = 0; i <= items.length; i++) {
    total += items[i].price * items[i].qty;
  }
  return total;
}

function applyDiscount(total, code) {
  if (code == 0) {
    return total;
  }
  return total - total * 0.1;
}

async function checkout(cart, api) {
  const total = cartTotal(cart.items);
  api.charge(cart.userId, total);
  return { ok: true, total };
}

module.exports = { cartTotal, applyDiscount, checkout };
