var socket = io();
var mediaRecorder;
var audioChunks = [];
const talkButton = document.getElementById('talk-button');

// Scroll chat to the bottom initially
document.addEventListener('DOMContentLoaded', (event) => {
    var chatHistory = document.querySelector('.chat-history');
    chatHistory.scrollTop = chatHistory.scrollHeight;
});

// Scroll to the bottom function for new messages
function scrollToBottom() {
    var chatHistory = document.querySelector('.chat-history');
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Listen for new chat updates
socket.on('update_chat', function(data) {
    var chatHistory = document.querySelector('.chat-history');
    chatHistory.innerHTML = '';  // Clear current chat history

    data.chat_history.forEach(function(message) {
        var nameClass = message.sender === 'Alice' ? 'name-chatbot' : 'name-user';
        chatHistory.innerHTML += `<p><strong class="${nameClass}">${message.sender}:</strong> ${message.message}</p>`;
    });

    scrollToBottom(); // Scroll to the bottom
});

// Listen for audio responses
socket.on('new_audio_response', function(data) {
    // Add a unique query parameter to avoid caching
    var uniqueAudioPath = data.audio_path + '?t=' + new Date().getTime();
    
    // Play audio response with the unique path
    var audio = new Audio(uniqueAudioPath);
    audio.play();

    // Delete audio file after it has finished playing
    audio.addEventListener('ended', function() {
        fetch('/delete_audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ audio_path: data.audio_path })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === "success") {
                console.log("Audio file deleted successfully.");
            } else {
                console.error("Error deleting audio file:", data.message);
            }
        })
        .catch(error => console.error("Fetch error:", error));
    });
});

// Initialize audio recording
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(function(stream) {
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = function(event) {
            audioChunks.push(event.data);
        };
    })
    .catch(function(error) {
        console.error('Error accessing microphone:', error);
    });

// Start recording on 'mousedown'
document.getElementById('talk-button').addEventListener('mousedown', function() {
    if (mediaRecorder) {
        audioChunks = []; // Reset audio chunks
        mediaRecorder.start();
        console.log('Recording started');
    }
});

// Stop recording on 'mouseup' and send to server
document.getElementById('talk-button').addEventListener('mouseup', function() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop(); // Stop recording
        console.log('Recording stopped');

        mediaRecorder.onstop = function() {
            var audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            audioChunks = []; // Reset for next recording

            var formData = new FormData();
            formData.append('audio', audioBlob, 'recording.wav');

            fetch('/process_audio', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => console.log('Server response:', data))
            .catch(error => console.error('Error:', error));
        };
    }
});

// Detect CTRL+SPACE to simulate the 'Talk' button
document.addEventListener('keydown', function(event) {
    if (event.ctrlKey && event.code === 'Space') {
        event.preventDefault(); // Prevent default space behavior
        document.getElementById('talk-button').dispatchEvent(new Event('mousedown'));
        talkButton.classList.add('active'); // Add active class (red color)
    }
});

document.addEventListener('keyup', function(event) {
    if (event.ctrlKey && event.code === 'Space') {
        event.preventDefault();
        document.getElementById('talk-button').dispatchEvent(new Event('mouseup'));
        talkButton.classList.remove('active'); // Release active class (red color)
    }
});
