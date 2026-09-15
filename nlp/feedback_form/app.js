const feedbackForm = document.getElementById("feedbackForm");
const complaintInput = document.getElementById("complaint");
const chat = document.getElementById("chat");


function addMessage(sender, message) {
    const messageElement = document.createElement("p");

    messageElement.innerHTML =
        `<strong>${sender}:</strong> ${message}`;

    chat.appendChild(messageElement);

    chat.scrollTop = chat.scrollHeight;
}


feedbackForm.addEventListener("submit", async function(event) {

    event.preventDefault();

    const complaint = complaintInput.value.trim();

    if (!complaint) {
        return;
    }


    // --------------------------------------------------------
    // Show user's message
    // --------------------------------------------------------

    addMessage("You", complaint);

    complaintInput.value = "";


    // --------------------------------------------------------
    // Show processing message
    // --------------------------------------------------------

    addMessage("AI", "Analyzing your complaint...");


    try {

        // ----------------------------------------------------
        // Send complaint to Python NLP API
        // ----------------------------------------------------

        const response = await fetch(
            "http://127.0.0.1:8000/nlp/parse",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    complaint: complaint
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

        console.log("NLP API response:");
        console.log(data);


        // ----------------------------------------------------
        // Remove "Analyzing..." message
        // ----------------------------------------------------

        const messages = chat.querySelectorAll("p");

        if (messages.length > 0) {
            messages[messages.length - 1].remove();
        }


        // ----------------------------------------------------
        // Handle successful HVAC constraint
        // ----------------------------------------------------

        if (
            data.status === "success" &&
            data.constraint
        ) {

            const constraint = data.constraint;

            const message =
                `I understood that <strong>${constraint.zone_id}</strong> ` +
                `needs <strong>${constraint.direction}</strong> ` +
                `${constraint.parameter} adjustment ` +
                `(${constraint.intensity}).`;

            addMessage("AI", message);

        }


        // ----------------------------------------------------
        // Handle clarification
        // ----------------------------------------------------

        else if (
            data.status === "clarification_required"
        ) {

            addMessage(
                "AI",
                data.message
            );

        }


        // ----------------------------------------------------
        // Handle unexpected response
        // ----------------------------------------------------

        else {

            addMessage(
                "AI",
                "I couldn't understand the response from the NLP service."
            );

        }

    }


    // --------------------------------------------------------
    // Handle connection/API errors
    // --------------------------------------------------------

    catch (error) {

        console.error("NLP API error:", error);

        // Remove "Analyzing..." message
        const messages = chat.querySelectorAll("p");

        if (messages.length > 0) {
            messages[messages.length - 1].remove();
        }

        addMessage(
            "AI",
            "I couldn't connect to the NLP service. Please make sure the Python API is running."
        );
    }

});
