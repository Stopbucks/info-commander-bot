// utils/summarizer.js
// 職責：處理降級邏輯 (事實報告、AI 補充、網路搜尋)

const { GoogleGenerativeAI } = require("@google/generative-ai");
const prompts = require('./prompts'); 
const common = require('./common-utils'); // 呼叫轉義工具

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

/**
 * 核心：優雅降級摘要器 (地端專用版)
 * @param {string} title - 影片標題
 * @param {string} description - 影片說明欄 (事實來源 3-a)
 * @param {string} status - 錯誤狀態 ('DOWNLOAD_FAILED' | 'TRANSCRIPTION_FAILED')
 */
async function getFallbackReport(title, description, status) {
    const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });

    // 3-a: 事實標註
    let statusLabel = status === 'DOWNLOAD_FAILED' ? "🥉 青銅級：YouTube 拒絕存取" : "🥈 白銀級：轉錄品質受限";
    
    // 3-c: 預留網路搜尋連結
    const searchQuery = encodeURIComponent(`${title} 內容摘要`);
    const searchLink = `[🔍 搜尋外部資料](https://www.google.com/search?q=${searchQuery})`;

    try {
        // ---------------------------------------------------------
        // (2) 預留地端 LLM 位置：未來只需在這裡切換模型呼叫
        // ---------------------------------------------------------
        // if (useLocalLLM) { return await callLocalLLM(title, description); }

        // (3) 目前統一由 Gemini 負責 (3-b: AI 知識庫補充)
        const prompt = `
            ${prompts.SUMMARY_SILVER}
            影片標題: ${title}
            目前事實 (說明欄): ${description || '無資料'}
            請根據標題與說明欄，提供 AI 知識庫的推測補充。
        `;

        const result = await model.generateContent(prompt);
        const aiSupplement = result.response.text();

        // 結構化輸出 (區分事實、AI、搜尋)
        return `
🚨 *${common.escapeMarkdownV2(title)}*
${statusLabel}

📊 *(3-a) 基本事實 (說明欄)*
${common.escapeMarkdownV2(description.substring(0, 150)) + '...'}

🧠 *(3-b) AI 知識補充*
${common.escapeMarkdownV2(aiSupplement)}

🌐 *(3-c) 進階搜尋*
${searchLink}
        `.trim();

    } catch (err) {
        return `⚠️ 嚴重錯誤：無法生成報告 - ${err.message}`;
    }
}

module.exports = { getFallbackReport };