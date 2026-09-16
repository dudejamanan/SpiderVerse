// ============================================================
// HVAC FEEDBACK FORM
// Connects the frontend to the FastAPI NLP service
// ============================================================


// ------------------------------------------------------------
// API URL
// ------------------------------------------------------------

const API_URL = "http://127.0.0.1:8000/nlp/chat";


// ------------------------------------------------------------
// Session ID
// ------------------------------------------------------------

// The backend uses a session ID to remember the conversation.
//
// We keep the same session ID while the user is interacting
// with the feedback form.

let sessionId = localStorage.getItem("hvac_session_id");


// ------------------------------------------------------------
// Get HTML elements
// ------------------------------------------------------------

const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send");
const chatBox = document.getElementById("chat");


// ------------------------------------------------------------
// Create a session ID on the frontend if one does not exist
// ------------------------------------------------------------

if (!sessionId) {

    sessionId = crypto.randomUUID();

    localStorage.setItem(
        "hvac_session_id",
        sessionId
    );
}


// ------------------------------------------------------------
// Add a message to the chat window
// ------------------------------------------------------------

function addMessage(sender, text) {

    const messageElement = document.createElement("div");

    messageElement.classList.add("message");

    if (sender === "user") {

        messageElement.classList.add("user-message");

        messageElement.innerHTML = `
            <strong>You:</strong> ${escapeHtml(text)}
        `;

    } else {

        messageElement.classList.add("assistant-message");

        messageElement.innerHTML = `
            <strong>HVAC Assistant:</strong> ${escapeHtml(text)}
        `;
    }

    chatBox.appendChild(messageElement);

    // Automatically scroll to the newest message.
    chatBox.scrollTop = chatBox.scrollHeight;
}


// ------------------------------------------------------------
// Safely display user/assistant text
// ------------------------------------------------------------

function escapeHtml(text) {

    const div = document.createElement("div");

    div.textContent = text;

    return div.innerHTML;
}


// ------------------------------------------------------------
// Display the structured HVAC constraint
// ------------------------------------------------------------

function displayConstraint(constraint) {

    if (!constraint) {
        return;
    }

    const constraintElement = document.createElement("div");

    constraintElement.classList.add(
        "constraint-message"
    );

    constraintElement.innerHTML = `
        <strong>HVAC Constraint</strong>
        <br>
        Zone: ${escapeHtml(String(constraint.zone_id ?? ""))}
        <br>
        Parameter: ${escapeHtml(String(constraint.parameter ?? ""))}
        <br>
        Direction: ${escapeHtml(String(constraint.direction ?? ""))}
        <br>
        Intensity: ${escapeHtml(String(constraint.intensity ?? ""))}
    `;

    chatBox.appendChild(constraintElement);

    chatBox.scrollTop = chatBox.scrollHeight;
}


// ------------------------------------------------------------
// Send message to FastAPI
// ------------------------------------------------------------

async function sendMessage() {

    const message = messageInput.value.trim();

    // Do not send an empty message.
    if (!message) {
        return;
    }


    // Show user's message immediately.
    addMessage(
        "user",
        message
    );


    // Clear input box.
    messageInput.value = "";


    // Disable button while request is being processed.
    sendButton.disabled = true;

    sendButton.textContent = "Sending...";


    try {

        // ----------------------------------------------------
        // Send HTTP POST request to FastAPI
        // ----------------------------------------------------

        const response = await fetch(
            API_URL,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    session_id: sessionId,
                    message: message
                })
            }
        );


        // ----------------------------------------------------
        // Check HTTP response
        // ----------------------------------------------------

        if (!response.ok) {

            throw new Error(
                `Server returned ${response.status}`
            );
        }


        // ----------------------------------------------------
        // Convert response to JSON
        // ----------------------------------------------------

        const data = await response.json();


        // ----------------------------------------------------
        // Save session ID returned by backend
        // ----------------------------------------------------

        if (data.session_id) {

            sessionId = data.session_id;

            localStorage.setItem(
                "hvac_session_id",
                sessionId
            );
        }


        // ----------------------------------------------------
        // Display assistant reply
        // ----------------------------------------------------

        if (data.reply) {

            addMessage(
                "assistant",
                data.reply
            );
        }


        // ----------------------------------------------------
        // Display structured constraint
        // ----------------------------------------------------

        if (data.constraint) {

            displayConstraint(
                data.constraint
            );
        }


        // ----------------------------------------------------
        // Debug information
        // ----------------------------------------------------

        console.log(
            "HVAC API response:",
            data
        );

    } catch (error) {

        console.error(
            "Error communicating with HVAC API:",
            error
        );


        addMessage(
            "assistant",
            "Sorry, I could not connect to the HVAC service. Please make sure the FastAPI server is running."
        );

    } finally {

        // Re-enable send button.
        sendButton.disabled = false;

        sendButton.textContent = "Send";

        // Put cursor back in input box.
        messageInput.focus();
    }
}


// ------------------------------------------------------------
// Send when button is clicked
// ------------------------------------------------------------

sendButton.addEventListener(
    "click",
    sendMessage
);


// ------------------------------------------------------------
// Send when Enter is pressed
// ------------------------------------------------------------

messageInput.addEventListener(
    "keydown",
    function (event) {

        if (event.key === "Enter") {

            event.preventDefault();

            sendMessage();
        }
    }
);