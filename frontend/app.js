
const form = document.getElementById("bookingForm");
const bookButton = document.getElementById("bookButton");
const statusMessage = document.getElementById("statusMessage");
const confirmation = document.getElementById("confirmation");

const departureDateInput = document.getElementById("departureDate");

// Prevent selecting a departure date in the past.
const today = new Date();
const localToday = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0")
].join("-");

departureDateInput.min = localToday;

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    statusMessage.textContent = "";
    confirmation.hidden = true;
    bookButton.disabled = true;
    bookButton.textContent = "Booking...";

    const booking = {
        name: document.getElementById("name").value.trim(),
        email: document.getElementById("email").value.trim(),
        age: Number(document.getElementById("age").value),
        departure_date: departureDateInput.value,
        source: document.getElementById("source").value.trim(),
        destination: document.getElementById("destination").value.trim()
    };

    try {
        const response = await fetch("/api/bookings", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(booking)
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Booking failed.");
        }

        const details = document.getElementById("bookingDetails");
        details.replaceChildren();

        const fields = [
            ["Passenger", result.booking.name],
            ["Email", result.booking.email],
            ["Age", result.booking.age],
            ["Departure date", result.booking.departure_date],
            ["Source", result.booking.source],
            ["Destination", result.booking.destination]
        ];

        fields.forEach(([label, value]) => {
            const paragraph = document.createElement("p");
            const strong = document.createElement("strong");

            strong.textContent = `${label}: `;
            paragraph.append(strong, document.createTextNode(String(value)));
            details.appendChild(paragraph);
        });

        confirmation.hidden = false;
        form.reset();
        departureDateInput.min = localToday;
        statusMessage.textContent = "";
        confirmation.scrollIntoView({ behavior: "smooth" });

    } catch (error) {
        statusMessage.textContent =
            `Booking failed: ${error.message}`;
    } finally {
        bookButton.disabled = false;
        bookButton.textContent = "Book Ticket";
    }
});

document.getElementById("newBookingButton").addEventListener("click", () => {
    confirmation.hidden = true;
    form.reset();
    departureDateInput.min = localToday;
    statusMessage.textContent = "";
    document.getElementById("name").focus();
});