/* HOTEL CESAR – scripts de interface (máscaras, confirmações, resumo, menu) */
(function () {
  "use strict";

  // ---------- Máscaras visuais de CPF e telefone ----------
  const mascaras = {
    cpf(v) {
      v = v.replace(/\D/g, "").slice(0, 11);
      return v.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
    },
    telefone(v) {
      v = v.replace(/\D/g, "").slice(0, 11);
      if (v.length <= 10) return v.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{4})(\d)/, "$1-$2");
      return v.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d)/, "$1-$2");
    },
  };
  document.querySelectorAll("[data-mask]").forEach((campo) => {
    const aplicar = () => { const f = mascaras[campo.dataset.mask]; if (f) campo.value = f(campo.value); };
    campo.addEventListener("input", aplicar);
    aplicar();
  });

  // ---------- Confirmação antes de ações destrutivas ----------
  document.querySelectorAll("form[data-confirmar]").forEach((form) => {
    form.addEventListener("submit", (e) => { if (!window.confirm(form.dataset.confirmar)) e.preventDefault(); });
  });

  // ---------- Linhas clicáveis ----------
  document.querySelectorAll("tr[data-href]").forEach((tr) => {
    tr.addEventListener("click", (e) => { if (!e.target.closest("a, button, form")) window.location = tr.dataset.href; });
  });

  // ---------- Menu lateral (celular/tablet) ----------
  const sidebar = document.getElementById("sidebar");
  document.querySelectorAll("[data-sidebar-toggle]").forEach((b) => b.addEventListener("click", () => sidebar && sidebar.classList.toggle("aberta")));

  // ---------- Navbar do site ao rolar ----------
  const nav = document.getElementById("siteNav");
  if (nav) {
    const onScroll = () => nav.classList.toggle("rolado", window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  // ---------- Resumo dinâmico da reserva ----------
  const dadosPrecos = document.getElementById("precos-quartos");
  const form = document.getElementById("formReserva");
  if (dadosPrecos && form && document.getElementById("resumoDinamico")) {
    const precos = JSON.parse(JSON.parse(dadosPrecos.textContent));
    const brl = (n) => n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    const campo = (n) => form.querySelector(`[name="${n}"]`);
    const el = (s) => form.querySelector(`[data-resumo-${s}]`);
    const atualizar = () => {
      const q = precos[campo("quarto").value];
      const ent = campo("data_checkin").value, sai = campo("data_checkout").value;
      const qtd = parseInt(campo("quantidade_hospedes").value || "0", 10);
      let diarias = 0;
      if (ent && sai) diarias = Math.round((new Date(sai) - new Date(ent)) / 86400000);
      const alerta = el("alerta");
      let msg = "";
      if (ent && sai && diarias <= 0) msg = "A data de saída deve ser posterior à entrada.";
      else if (q && qtd > q.capacidade) msg = `Este quarto comporta no máximo ${q.capacidade} hóspede(s).`;
      alerta.textContent = msg;
      alerta.classList.toggle("d-none", !msg);
      el("diarias").textContent = diarias > 0 ? diarias : "—";
      el("diaria").textContent = q ? brl(parseFloat(q.diaria)) : "—";
      el("total").textContent = q && diarias > 0 ? brl(parseFloat(q.diaria) * diarias) : "—";
    };
    ["quarto", "data_checkin", "data_checkout", "quantidade_hospedes"].forEach((n) => campo(n) && campo(n).addEventListener("input", atualizar));
    form.addEventListener("change", atualizar);
    atualizar();
  }
})();
