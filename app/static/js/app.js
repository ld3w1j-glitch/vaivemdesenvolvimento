function criarIconeMercado(cor) {
  const corFinal = cor || "#1f8a4c";

  return L.divIcon({
    className: "custom-market-marker",
    html: `
      <div style="
        width: 36px;
        height: 36px;
        background: ${corFinal};
        border: 3px solid #ffffff;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        box-shadow: 0 6px 16px rgba(0,0,0,.28);
        position: relative;
      ">
        <div style="
          width: 12px;
          height: 12px;
          background: #ffffff;
          border-radius: 50%;
          position: absolute;
          top: 9px;
          left: 9px;
        "></div>
      </div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 36],
    popupAnchor: [0, -32]
  });
}

function montarPopupMercado(m) {
  const corPrimaria = m.corPrimaria || "#1f8a4c";
  const corSecundaria = m.corSecundaria || "#e8f5ec";

  const avatar = m.fotoPerfil
    ? `<img src="${m.fotoPerfil}" alt="Foto do mercado">`
    : `🏪`;

  const capa = m.fotoApresentacao
    ? `<img src="${m.fotoApresentacao}" alt="Foto de apresentação">`
    : `
      <div class="popup-capa-placeholder" style="background:${corSecundaria}; color:${corPrimaria};">
        ${m.nome}
      </div>
    `;

  return `
    <div class="market-popup-card">
      <div class="market-popup-cover">
        ${capa}
      </div>

      <div class="market-popup-body">
        <div class="market-popup-header">
          <div class="market-popup-avatar" style="border-color:${corPrimaria}; background:${corSecundaria};">
            ${avatar}
          </div>

          <div class="market-popup-main">
            <h3 style="color:${corPrimaria};">${m.nome}</h3>
            <span class="market-popup-badge" style="background:${corSecundaria}; color:${corPrimaria};">
              ${m.horario || "Horário não informado"}
            </span>
          </div>
        </div>

        <div class="market-popup-info">
          <div class="popup-line">
            <span class="popup-icon">📍</span>
            <span>${m.endereco || "Endereço não informado"}</span>
          </div>

          <div class="popup-line">
            <span class="popup-icon">📞</span>
            <span>${m.telefone || "Telefone não informado"}</span>
          </div>
        </div>

        <a class="market-popup-btn" href="${m.url}" style="background:${corPrimaria};">
          Entrar no mercado
        </a>
      </div>
    </div>
  `;
}

function initMarketMap(mercados) {
  const mapElement = document.getElementById("map");

  if (!mapElement) {
    return;
  }

  const center = mercados.length
    ? [mercados[0].lat, mercados[0].lng]
    : [-22.228, -45.936];

  const map = L.map("map").setView(center, 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap"
  }).addTo(map);

  const markers = {};

  mercados.forEach((m) => {
    const marker = L.marker([m.lat, m.lng], {
      icon: criarIconeMercado(m.corPonteiro)
    }).addTo(map);

    marker.bindPopup(montarPopupMercado(m), {
      maxWidth: 340,
      minWidth: 280,
      className: "market-popup-wrap"
    });

    marker.on("click", () => {
      selecionarMercadoNaLista(m.id);
    });

    markers[m.id] = marker;
  });

  function focarMercado(id) {
    const mercado = mercados.find((m) => String(m.id) === String(id));

    if (!mercado || !markers[id]) {
      return;
    }

    map.setView([mercado.lat, mercado.lng], 17, {
      animate: true
    });

    markers[id].openPopup();
    selecionarMercadoNaLista(id);
  }

  function selecionarMercadoNaLista(id) {
    document.querySelectorAll(".mercado-lista-btn").forEach((btn) => {
      btn.classList.remove("ativo");

      if (String(btn.dataset.id) === String(id)) {
        btn.classList.add("ativo");
      }
    });
  }

  document.querySelectorAll(".mercado-lista-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      focarMercado(btn.dataset.id);
    });
  });

  setTimeout(() => {
    map.invalidateSize();

    if (mercados.length) {
      focarMercado(mercados[0].id);
    }
  }, 300);
}
