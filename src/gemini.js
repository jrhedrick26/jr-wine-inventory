import { GoogleGenAI } from '@google/genai';

/**
 * Strips the data URL prefix from a base64 string
 */
function cleanBase64(base64Str) {
  if (base64Str.startsWith('data:')) {
    return base64Str.split(',')[1];
  }
  return base64Str;
}

/**
 * Scans a base64 wine label image using Gemini 2.5 Flash and extracts details in structured JSON
 */
export async function scanWineLabel(apiKey, base64Image, mimeType = 'image/jpeg') {
  if (!apiKey) throw new Error("Gemini API Key is required. Please set it in Settings.");

  const ai = new GoogleGenAI({ apiKey });
  const rawBase64 = cleanBase64(base64Image);

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: [
        {
          inlineData: {
            data: rawBase64,
            mimeType: mimeType
          }
        },
        "Scan this wine label photo. Extract the name of the wine, the vintage year (if not visible or non-vintage, use 'N/A'), and the varietal or grape type. Return the results in structured JSON."
      ],
      config: {
        responseMimeType: 'application/json',
        responseSchema: {
          type: 'OBJECT',
          properties: {
            name: { 
              type: 'STRING', 
              description: 'The name/producer of the wine (e.g., Caymus, Chateau Margaux, Penfolds Bin 389)' 
            },
            year: { 
              type: 'STRING', 
              description: 'The vintage year (e.g., 2018, 2021). Use N/A if it is a non-vintage wine.' 
            },
            varietal: { 
              type: 'STRING', 
              description: 'The varietal or grape blend (e.g., Cabernet Sauvignon, Chardonnay, Bordeaux Blend)' 
            }
          },
          required: ['name', 'year', 'varietal']
        }
      }
    });

    const text = response.text;
    console.log("Raw Gemini OCR response:", text);
    return JSON.parse(text);
  } catch (error) {
    console.error("Gemini Scan Error:", error);
    throw new Error("Failed to parse label. Make sure the photo is clear and try again.");
  }
}

/**
 * Generates a response for the Sommelier Chat Assistant
 * @param {string} apiKey - Users Gemini API Key
 * @param {Array} chatHistory - Array of objects containing { role: 'user'|'model', text: string }
 * @param {Array} activeInventory - The user's current wine stock
 * @param {Array} historyLog - The list of wines the user has drank previously
 */
export async function getSommelierChatResponse(apiKey, chatHistory, activeInventory = [], historyLog = []) {
  if (!apiKey) throw new Error("Gemini API Key is required. Please set it in Settings.");

  const ai = new GoogleGenAI({ apiKey });

  // Format inventory details for context
  const inventoryContext = activeInventory.length > 0 
    ? activeInventory.map(w => `- ${w.name} (${w.year}) - ${w.varietal}`).join('\n')
    : "No bottles in active inventory.";

  const historyContext = historyLog.length > 0
    ? historyLog.map(w => `- ${w.name} (${w.year}) - ${w.varietal} (drank on ${w.poppedAt ? new Date(w.poppedAt.toDate()).toLocaleDateString() : 'unknown date'})`).join('\n')
    : "No bottles in drinking history.";

  const systemInstruction = `You are a knowledgeable, charming, and refined AI Sommelier.
Your goal is to help the user manage, pair, and enjoy their private wine cellar.
You have access to the user's live cellar inventory and history of previously consumed bottles:

[ACTIVE CELLAR INVENTORY]
${inventoryContext}

[PREVIOUSLY CONSUMED BOTTLES]
${historyContext}

Guidelines:
1. Provide personalized food pairing recommendations based on what is CURRENTLY in their active inventory.
2. If they ask "What should I drink tonight?", suggest 1-2 specific bottles from their ACTIVE inventory and explain why they are great choices (referencing potential food pairings or vintage details).
3. If they ask about a bottle they drank before, refer to their history log.
4. Keep answers relatively concise and highly conversational (perfect for a mobile viewport screen).
5. Suggest wine serving temperatures or aeration recommendations when relevant.
6. If the active cellar is empty, encourage them to scan a bottle using their camera first.
7. NEVER suggest bottles they do not have in their active inventory unless they explicitly ask for general recommendations outside their cellar.`;

  try {
    // Map conversation history to the API schema
    // Google Gen AI SDK expects [{ role: 'user'|'model', parts: [{ text: string }] }]
    const apiContents = chatHistory.map(msg => ({
      role: msg.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: msg.text }]
    }));

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: apiContents,
      config: {
        systemInstruction: systemInstruction,
        temperature: 0.7
      }
    });

    return response.text;
  } catch (error) {
    console.error("Gemini Chat Error:", error);
    throw new Error("I had trouble reaching the cellar. Please try again in a moment.");
  }
}
