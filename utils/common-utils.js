// ==================================================
// 🛠️ Telegram MarkdownV2 轉義工具
// ==================================================
function escapeMarkdownV2(text) {
    if (!text) return '';
    // 核心技術：使用正則表達式批次處理 Telegram 敏感字元
    return text.replace(/[_*[\]()~`>#+\-=|{}.!]/g, '\\$&');
}

// ==================================================
// 🛠️ move from server part : Telegram MarkdownV2 轉義工具
// ==================================================

// utils/common-utils.js

/**
 * 🛡️ Telegram MarkdownV2 轉義工具
 */
function escapeMarkdownV2(text) {
    if (!text) return '';
    return text.replace(/[_*[\]()~`>#+\-=|{}.!]/g, '\\$&');
}

/**
 * 🏗️ 訊息組裝器：將 AI 內容與連結合併
 */
function buildFinalMessage(content, references) {
    let body = escapeMarkdownV2(content); // 內部呼叫轉義
    let refSection = "";
    if (references && references.length > 0) {
        refSection += "\n\n📚 *參考資料*\n";
        references.forEach(item => {
            let safeTitle = escapeMarkdownV2(item.title);
            refSection += `• [${safeTitle}](${item.link})\n`;
        });
    }
    return body + refSection;
}

module.exports = {
    escapeMarkdownV2,
    buildFinalMessage
};