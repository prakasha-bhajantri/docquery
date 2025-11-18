app_name = "DocQuery - Chat with your document"

a ="""
<style>
/* --- 0. Font Imports --- */
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');

/* --- 1. CENTER "TEST" LABEL IN HEADER --- */
header[data-testid="stHeader"]::after {
    content: "DocQuery - Chat with your document";
    position: fixed; 
    left: 60%; 
    transform: translateX(-50%); 
    top: 15px; 
    font-weight: 900;
    font-size: 1.5rem;
    color: #FF4B4B;
    z-index: 99999;
    pointer-events: none;
}

/* --- 2. CHAT BUBBLES (Fixed Alignment) --- */

/* USER BUBBLE (Right Aligned) */
div[data-testid="stChatMessage"][data-author="user"] {
    /* Swap avatar and text */
    flex-direction: row-reverse !important;
    /* Align the whole container to the right */
    justify-content: flex-end !important;
    /* Ensure text aligns right inside the container */
    text-align: right !important;
}

/* User Bubble Content Box */
div[data-testid="stChatMessage"][data-author="user"] > div:first-child {
    /* Avatar margins */
    margin-left: 10px !important;
    margin-right: 0 !important;
}

div[data-testid="stChatMessage"][data-author="user"] > div:last-child > div {
    background-color: #007AFF;
    color: white;
    padding: 10px 15px;
    border-radius: 20px 4px 20px 20px;
    
    /* Force the box to the right side of the flex container */
    margin-left: auto !important;
    margin-right: 0 !important;
}

/* ASSISTANT BUBBLE (Left Aligned) */
div[data-testid="stChatMessage"][data-author="assistant"] {
    /* Default direction */
    flex-direction: row !important;
    /* Align the whole container to the left */
    justify-content: flex-start !important;
    text-align: left !important;
}

/* Assistant Bubble Content Box */
div[data-testid="stChatMessage"][data-author="assistant"] > div:last-child > div {
    background-color: #262730;
    color: #E0E0E0;
    padding: 10px 15px;
    border-radius: 4px 20px 20px 20px;
    
    /* Force the box to the left side */
    margin-right: auto !important;
    margin-left: 0 !important;
}

/* --- 3. CHAT INPUT & LAYOUT --- */
.block-container {
    padding-top: 3rem;
    padding-bottom: 5rem;
    max-width: 1200px; 
    margin: auto;
}

.stChatInput {
    padding-bottom: 1rem;
}

/* Hide footer */
footer { display: none !important; }
</style>
"""