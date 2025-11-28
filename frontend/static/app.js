document.addEventListener("DOMContentLoaded", () => {
  const incomingTextEl = document.getElementById("incomingText");
  const emailStyleEl = document.getElementById("emailStyle");
  const emailLengthEl = document.getElementById("emailLength");
  const generateBtn = document.getElementById("generateBtn");
  const copyBtn = document.getElementById("copyBtn");
  const sendBtn = document.getElementById("sendBtn");
  const regenerateBtn = document.getElementById("regenerateBtn");

  const classificationBlock = document.getElementById("classificationBlock");
  const extractedInfoBlock = document.getElementById("extractedInfoBlock");
  const answerTextEl = document.getElementById("answerText");
  const statusBar = document.getElementById("statusBar");

  const exampleButtons = document.querySelectorAll(".chip[data-example]");

  let lastRequestPayload = null;
  let isLoading = false;

  function setStatus(message, type) {
    statusBar.textContent = message;
    statusBar.classList.remove("status-info", "status-success", "status-error");
    statusBar.classList.add(`status-${type || "info"}`);
  }

  function setLoading(value) {
    isLoading = value;
    generateBtn.disabled = value;
    regenerateBtn.disabled = value;
    generateBtn.textContent = value ? "Генерация…" : "Сгенерировать ответ";
  }

  function renderClassification(classification) {
    if (!classification) {
      classificationBlock.innerHTML = `
        <div class="placeholder">
          Классификация появится после генерации ответа.
        </div>
      `;
      return;
    }

    classificationBlock.innerHTML = `
      <div class="badge">${classification}</div>
    `;
  }

  function renderExtractedInfo(items) {
    if (!items || !items.length) {
      extractedInfoBlock.innerHTML = `
        <div class="placeholder">
          Ключевые факты будут показаны после анализа письма.
        </div>
      `;
      return;
    }

    const listHtml = items
      .map(
        (item) => `
      <li>
        <span class="info-label">${item.label}:</span>
        <span class="info-value"> ${item.value}</span>
      </li>
    `
      )
      .join("");

    extractedInfoBlock.innerHTML = `
      <ul class="info-list">
        ${listHtml}
      </ul>
    `;
  }

  async function sendGenerateRequest(payload) {
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const msg = errData.error || "Ошибка при генерации ответа.";
        throw new Error(msg);
      }

      return await response.json();
    } catch (e) {
      throw e;
    }
  }

  async function handleGenerate() {
    const text = incomingTextEl.value.trim();
    if (!text) {
      setStatus("Введите текст входящего письма.", "error");
      return;
    }

    const payload = {
      incomingText: text,
      emailStyle: emailStyleEl.value,
      emailLength: emailLengthEl.value,
    };

    lastRequestPayload = payload;

    setLoading(true);
    setStatus("Генерируем ответ…", "info");

    try {
      const data = await sendGenerateRequest(payload);

      renderClassification(data.classification);
      renderExtractedInfo(data.extractedInfo || []);
      answerTextEl.value = data.answerText || "";

      setStatus("Ответ успешно сгенерирован.", "success");
    } catch (e) {
      console.error(e);
      setStatus(e.message || "Не удалось сгенерировать ответ.", "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy() {
    const text = answerTextEl.value.trim();
    if (!text) {
      setStatus("Нет текста ответа для копирования.", "error");
      return;
    }

    try {
      await navigator.clipboard.writeText(text);
      setStatus("Ответ скопирован в буфер обмена.", "success");
    } catch (e) {
      setStatus("Не удалось скопировать текст. Скопируйте вручную.", "error");
    }
  }

  function handleMockSend() {
    const text = answerTextEl.value.trim();
    if (!text) {
      setStatus("Нет текста ответа для отправки.", "error");
      return;
    }
    // Здесь мог бы быть вызов почтового сервиса
    setStatus("Ответ отправлен (эмуляция).", "success");
  }

  async function handleRegenerate() {
    if (!lastRequestPayload) {
      // Если ещё ни разу не генерировали — просто вызвать обычную генерацию
      await handleGenerate();
      return;
    }

    await handleGenerate();
  }

  function handleExampleClick(type) {
    if (type === "complaint") {
      incomingTextEl.value =
        "ООО «Пример-Банк»\n\n" +
        "Настоящим направляем официальную жалобу по факту некорректного списания средств по договору № 123/45 от 15.09.2025. " +
        "Просим в срок до 30.11.2025 предоставить письменный ответ с результатами проверки.";
    } else if (type === "regulator") {
      incomingTextEl.value =
        "Банк «Пример»\n\n" +
        "Направляем регуляторный запрос в рамках проверки соблюдения требований законодательства. " +
        "Просим до 10.12.2025 предоставить пояснения и копии документов по операциям клиента ООО «Альфа».";
    } else if (type === "partner") {
      incomingTextEl.value =
        "АО «Партнёр»\n\n" +
        "Предлагаем рассмотреть возможность запуска совместного проекта по кобрендинговой карте. " +
        "Готовы направить детальную презентацию и обсудить условия сотрудничества.";
    }

    setStatus("Пример письма подставлен. Нажмите «Сгенерировать ответ».", "info");
  }

  generateBtn.addEventListener("click", () => {
    if (!isLoading) {
      handleGenerate();
    }
  });

  copyBtn.addEventListener("click", handleCopy);
  sendBtn.addEventListener("click", handleMockSend);
  regenerateBtn.addEventListener("click", () => {
    if (!isLoading) {
      handleRegenerate();
    }
  });

  exampleButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const type = btn.getAttribute("data-example");
      handleExampleClick(type);
    });
  });
});
