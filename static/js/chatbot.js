// Enhanced Chatbot with Interactive Buttons, Voice Features, and Complete Booking Flow

document.addEventListener('DOMContentLoaded', function() {
    const chatbotButton = document.getElementById('chatbot-button');
    const chatbotWindow = document.getElementById('chatbot-window');
    const chatbotClose = document.getElementById('chatbot-close');
    const chatbotForm = document.getElementById('chatbot-form');
    const chatbotInput = document.getElementById('chatbot-input');
    const chatbotMessages = document.getElementById('chatbot-messages');
    const voiceBtn = document.getElementById('chatbot-voice-btn');
    const voiceIndicator = document.getElementById('voice-recording-indicator');
    
    // Voice recording variables
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    // Function to handle button clicks (defined early so it can be used by initial buttons)
    async function handleButtonClick(button, previousData = {}) {
        const action = button.action;
        const value = button.value;
        const bookingId = button.booking_id;
        const paymentType = button.payment_type;
        const url = button.url;
        const text = button.text || button.innerHTML || '';
        
        // If button has URL, navigate
        if (url && (action === 'login' || action === 'view_bookings' || action === 'pay_online')) {
            window.location.href = url;
            return;
        }
        
        // Show user's selection
        appendMessage(text || action, 'user');
        
        // Show typing indicator
        const typingIndicator = appendMessage('...', 'bot typing');
        
        try {
            let requestBody = {};
            
            // Handle different actions
            if (action === 'start_booking') {
                requestBody = { action: 'start_booking' };
            } else if (action === 'check_availability') {
                requestBody = {
                    action: 'check_availability',
                    date: value || 'tomorrow'
                };
            } else if (action === 'help') {
                requestBody = { message: 'help' };
            } else if (action === 'select_date') {
                requestBody = {
                    action: 'select_date',
                    date: value,
                    step: 'select_date',
                    booking_data: previousData.booking_data || {}
                };
            } else if (action === 'select_time') {
                requestBody = {
                    action: 'select_time',
                    time_slot: value,
                    step: 'select_time',
                    booking_data: previousData.booking_data || {}
                };
            } else if (action === 'select_visitors') {
                requestBody = {
                    action: 'select_visitors',
                    visitors: value,
                    step: 'select_visitors',
                    booking_data: previousData.booking_data || {}
                };
            } else if (action === 'confirm_and_pay') {
                // Get booking_data from previous response or try to reconstruct from previousData
                let bookingData = previousData.booking_data || lastBookingData || {};
                
                // If booking_data is empty, try to get from the last message's data
                if (!bookingData.date || !bookingData.time_slot || !bookingData.visitors) {
                    // Try to extract from previousData if available
                    if (previousData.date) bookingData.date = previousData.date;
                    if (previousData.time_slot) bookingData.time_slot = previousData.time_slot;
                    if (previousData.visitors) bookingData.visitors = previousData.visitors;
                    
                    // If still missing, try to get from lastBookingData
                    if (!bookingData.date && lastBookingData.date) bookingData.date = lastBookingData.date;
                    if (!bookingData.time_slot && lastBookingData.time_slot) bookingData.time_slot = lastBookingData.time_slot;
                    if (!bookingData.visitors && lastBookingData.visitors) bookingData.visitors = lastBookingData.visitors;
                }
                
                requestBody = {
                    action: 'confirm_and_pay',
                    payment_type: paymentType,
                    booking_data: bookingData
                };
            } else if (action === 'change_to_cash') {
                requestBody = {
                    action: 'change_to_cash',
                    booking_id: bookingId
                };
            } else if (action === 'book_from_availability') {
                requestBody = {
                    action: 'book_from_availability',
                    date: button.date || value,
                    time_slot: button.time_slot || value
                };
            } else if (action === 'pay_online' || action === 'view_bookings' || action === 'login') {
                if (url) {
                    window.location.href = url;
                    return;
                }
            } else {
                // Default: send as message
                requestBody = { message: text || action };
            }
            
            const response = await fetch('/chatbot', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
            
            const data = await response.json();
            
            typingIndicator.remove();
            appendMessageWithButtons(data.response, 'bot', data.buttons, data);
            
        } catch (error) {
            console.error('Error:', error);
            typingIndicator.remove();
            appendMessage('Sorry, I encountered an error. Please try again.', 'bot error');
        }
    }

    // Initialize quick action buttons in welcome message
    if (chatbotMessages && chatbotMessages.querySelector('.chatbot-buttons')) {
        const quickActionButtons = chatbotMessages.querySelectorAll('.chatbot-buttons .chatbot-button');
        quickActionButtons.forEach(btn => {
            btn.addEventListener('click', async function() {
                const action = this.dataset.action;
                const value = this.dataset.value;
                const buttonData = {
                    action: action,
                    value: value,
                    text: this.textContent || this.innerHTML
                };
                await handleButtonClick(buttonData, {});
            });
        });
    }

    // Toggle chatbot window
    if (chatbotButton) {
        chatbotButton.addEventListener('click', function() {
            chatbotWindow.style.display = chatbotWindow.style.display === 'none' ? 'flex' : 'none';
            if (chatbotWindow.style.display === 'flex') {
                chatbotInput.focus();
            }
        });
    }

    // Close chatbot window
    if (chatbotClose) {
        chatbotClose.addEventListener('click', function() {
            chatbotWindow.style.display = 'none';
        });
    }

    // Handle form submission
    if (chatbotForm) {
        chatbotForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const userMessage = chatbotInput.value.trim();
            if (!userMessage) return;

            // Add user message to chat
            appendMessage(userMessage, 'user');
            chatbotInput.value = '';
            
            // Show typing indicator
            const typingIndicator = appendMessage('...', 'bot typing');
            
            try {
                await processMessage(userMessage, typingIndicator);
            } catch (error) {
                console.error('Error:', error);
                typingIndicator.remove();
                appendMessage('Sorry, I encountered an error. Please try again later.', 'bot error');
            }
        });
    }

    // Function to process messages
    async function processMessage(userMessage, typingIndicator) {
        const lowerMessage = userMessage.toLowerCase();
        let requestBody = { message: userMessage };
        
        // Check for booking intent
        if (lowerMessage.includes('book') || lowerMessage.includes('reserve') || lowerMessage.includes('ticket')) {
            requestBody = { action: 'start_booking' };
        }
        // Check for availability
        else if (lowerMessage.includes('availability') || lowerMessage.includes('available') || lowerMessage.includes('check')) {
            const dateMatch = userMessage.match(/(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|today|tomorrow)/i);
            if (dateMatch) {
                requestBody = {
                    action: 'check_availability',
                    date: dateMatch[1].toLowerCase()
                };
            }
        }
        
        const response = await fetch('/chatbot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();
        
        // Remove typing indicator
        typingIndicator.remove();
        
        // Add bot response with buttons if available
        appendMessageWithButtons(data.response, 'bot', data.buttons, data);
        
        // Handle special actions
        if (data.requires_login) {
            setTimeout(() => {
                appendMessageWithButtons('🔗 Please log in to continue.', 'bot', data.buttons || [
                    {text: "🔗 Log In", action: "login", url: "/login"}
                ]);
            }, 500);
        }
        
        if (data.success && data.booking) {
            // Booking successful - already handled in appendMessageWithButtons
        }
        
        if (data.payment_required && data.buttons) {
            // Payment required - buttons already shown
        }
    }

    // Store the last booking data globally to ensure it's available for button clicks
    let lastBookingData = {};
    
    // Function to append messages with interactive buttons
    function appendMessageWithButtons(text, sender, buttons, data = {}) {
        const messageDiv = document.createElement('div');
        
        // Store booking_data if available for later use
        if (data.booking_data) {
            lastBookingData = data.booking_data;
        }
        
        // Add special classes based on step or success
        let messageClass = `message ${sender}`;
        if (data.step) {
            messageClass += ' booking-step';
        }
        if (data.success) {
            messageClass += ' booking-confirmation';
        }
        if (data.error) {
            messageClass += ' booking-error';
        }
        
        messageDiv.className = messageClass;
        
        // Format message with line breaks and markdown-style formatting
        let formattedText = text
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #ff00ff;">$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        messageDiv.innerHTML = formattedText;
        
        chatbotMessages.appendChild(messageDiv);
        
        // Add buttons if available
        if (buttons && Array.isArray(buttons) && buttons.length > 0) {
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'chatbot-buttons';
            
            // Add suggestions class for suggestion buttons
            if (buttons.length > 3) {
                buttonContainer.classList.add('suggestions');
            }
            
            buttons.forEach(button => {
                const btn = document.createElement('button');
                btn.className = 'chatbot-button';
                btn.innerHTML = button.text;
                btn.dataset.action = button.action;
                btn.dataset.value = button.value || '';
                btn.dataset.bookingId = button.booking_id || '';
                btn.dataset.paymentType = button.payment_type || '';
                
                if (button.url) {
                    btn.dataset.url = button.url;
                }
                
                // Store the full data object with the button for later retrieval
                btn.dataset.messageData = JSON.stringify(data);
                
                btn.addEventListener('click', async function() {
                    // Try to get data from the button's stored data, or use the passed data
                    let buttonData = data;
                    try {
                        const storedData = this.dataset.messageData;
                        if (storedData) {
                            buttonData = JSON.parse(storedData);
                        }
                    } catch (e) {
                        console.log('Could not parse stored data, using passed data');
                    }
                    await handleButtonClick(button, buttonData);
                });
                
                buttonContainer.appendChild(btn);
            });
            
            messageDiv.appendChild(buttonContainer);
        }
        
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        return messageDiv;
    }


    // Function to append simple messages
    function appendMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        
        const formattedText = text.replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
        messageDiv.innerHTML = formattedText;
        
        chatbotMessages.appendChild(messageDiv);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        
        return messageDiv;
    }

    // Allow Enter key to send message
    if (chatbotInput) {
        chatbotInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                chatbotForm.dispatchEvent(new Event('submit'));
            }
        });
    }
});

// Also handle the standalone chatbot page
if (document.getElementById('chat-form')) {
    const chatForm = document.getElementById('chat-form');
    const chatMessages = document.getElementById('chat-messages');
    
    // Store the last booking data globally to ensure it's available for button clicks
    let lastBookingData = {};

    function appendMessage(text, sender) {
        const msg = document.createElement('div');
        msg.className = 'message ' + sender;
        
        const formattedText = text.replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #ff00ff;">$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
        msg.innerHTML = formattedText;
        
        chatMessages.appendChild(msg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return msg;
    }
    
    function appendMessageWithButtons(text, sender, buttons, data = {}) {
        const msg = document.createElement('div');
        
        // Store booking_data if available for later use
        if (data.booking_data) {
            lastBookingData = data.booking_data;
        }
        
        // Add special classes based on step or success
        let messageClass = 'message ' + sender;
        if (data.step) {
            messageClass += ' booking-step';
        }
        if (data.success) {
            messageClass += ' booking-confirmation';
        }
        if (data.error) {
            messageClass += ' booking-error';
        }
        msg.className = messageClass;
        
        const formattedText = text.replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #ff00ff;">$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
        msg.innerHTML = formattedText;
        
        if (buttons && Array.isArray(buttons) && buttons.length > 0) {
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'chatbot-buttons';
            
            // Add suggestions class for suggestion buttons
            if (buttons.length > 3) {
                buttonContainer.classList.add('suggestions');
            }
            
            buttons.forEach(button => {
                const btn = document.createElement('button');
                btn.className = 'chatbot-button';
                btn.innerHTML = button.text;
                btn.dataset.action = button.action;
                btn.dataset.value = button.value || '';
                btn.dataset.bookingId = button.booking_id || '';
                btn.dataset.paymentType = button.payment_type || '';
                
                if (button.url) {
                    btn.dataset.url = button.url;
                }
                
                // Store the full data object with the button for later retrieval
                btn.dataset.messageData = JSON.stringify(data);
                
                btn.addEventListener('click', async function() {
                    // Try to get data from the button's stored data, or use the passed data
                    let buttonData = data;
                    try {
                        const storedData = this.dataset.messageData;
                        if (storedData) {
                            buttonData = JSON.parse(storedData);
                        }
                    } catch (e) {
                        console.log('Could not parse stored data, using passed data');
                    }
                    await handleButtonClick(button, buttonData);
                });
                
                buttonContainer.appendChild(btn);
            });
            
            msg.appendChild(buttonContainer);
        }
        
        chatMessages.appendChild(msg);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return msg;
    }
    
    // Function to handle button clicks (same as floating widget)
    async function handleButtonClick(button, previousData = {}) {
        const action = button.action;
        const value = button.value;
        const bookingId = button.booking_id;
        const paymentType = button.payment_type;
        const url = button.url;
        
        // If button has URL, navigate
        if (url && (action === 'login' || action === 'view_bookings' || action === 'pay_online')) {
            window.location.href = url;
            return;
        }
        
        // Show user's selection
        appendMessage(button.text, 'user');
        
        // Show typing indicator
        const typingIndicator = appendMessage('...', 'bot typing');
        
        try {
            let requestBody = {};
            
            // Handle different actions
            if (action === 'start_booking') {
                requestBody = { action: 'start_booking' };
            } else if (action === 'select_date') {
                requestBody = {
                    action: 'select_date',
                    date: value,
                    step: 'select_date',
                    booking_data: previousData.booking_data || {}
                };
            } else if (action === 'select_time') {
                requestBody = {
                    action: 'select_time',
                    time_slot: value,
                    step: 'select_time',
                    booking_data: previousData.booking_data || {}
                };
            } else if (action === 'select_visitors') {
                requestBody = {
                    action: 'select_visitors',
                    visitors: value,
                    step: 'select_visitors',
                    booking_data: previousData.booking_data || {}
                };
            } else if (action === 'confirm_and_pay') {
                // Get booking_data from previous response or try to reconstruct from previousData
                let bookingData = previousData.booking_data || lastBookingData || {};
                
                // If booking_data is empty, try to get from the last message's data
                if (!bookingData.date || !bookingData.time_slot || !bookingData.visitors) {
                    // Try to extract from previousData if available
                    if (previousData.date) bookingData.date = previousData.date;
                    if (previousData.time_slot) bookingData.time_slot = previousData.time_slot;
                    if (previousData.visitors) bookingData.visitors = previousData.visitors;
                    
                    // If still missing, try to get from lastBookingData
                    if (!bookingData.date && lastBookingData.date) bookingData.date = lastBookingData.date;
                    if (!bookingData.time_slot && lastBookingData.time_slot) bookingData.time_slot = lastBookingData.time_slot;
                    if (!bookingData.visitors && lastBookingData.visitors) bookingData.visitors = lastBookingData.visitors;
                }
                
                requestBody = {
                    action: 'confirm_and_pay',
                    payment_type: paymentType,
                    booking_data: bookingData
                };
            } else if (action === 'change_to_cash') {
                requestBody = {
                    action: 'change_to_cash',
                    booking_id: bookingId
                };
            } else if (action === 'check_availability') {
                requestBody = {
                    action: 'check_availability',
                    date: value
                };
            } else if (action === 'book_from_availability') {
                requestBody = {
                    action: 'book_from_availability',
                    date: button.date || value,
                    time_slot: button.time_slot || value
                };
            } else if (action === 'help') {
                requestBody = { message: 'help' };
            } else if (action === 'pay_online' || action === 'view_bookings' || action === 'login') {
                if (url) {
                    window.location.href = url;
                    return;
                }
            } else {
                // Default: send as message
                requestBody = { message: button.text };
            }
            
            const response = await fetch('/chatbot', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
            
            const responseData = await response.json();
            
            typingIndicator.remove();
            appendMessageWithButtons(responseData.response, 'bot', responseData.buttons, responseData);
            
        } catch (error) {
            console.error('Error:', error);
            typingIndicator.remove();
            appendMessage('Sorry, I encountered an error. Please try again.', 'bot error');
        }
    }
    
    // Initialize quick action buttons in welcome message
    if (chatMessages && chatMessages.querySelector('.chatbot-buttons')) {
        const quickActionButtons = chatMessages.querySelectorAll('.chatbot-buttons .chatbot-button');
        quickActionButtons.forEach(btn => {
            btn.addEventListener('click', async function() {
                const action = this.dataset.action;
                const value = this.dataset.value;
                const buttonData = {
                    action: action,
                    value: value,
                    text: this.textContent || this.innerHTML
                };
                await handleButtonClick(buttonData, {});
            });
        });
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = document.getElementById('user-input');
        const userText = input.value.trim();
        
        if (!userText) return;
        
        appendMessage(userText, 'user');
        input.value = '';
        
        const typingIndicator = appendMessage('...', 'bot typing');
        
        try {
            const lowerMessage = userText.toLowerCase();
            let requestBody = { message: userText };
            
            // Check for booking intent
            if (lowerMessage.includes('book') || lowerMessage.includes('reserve') || lowerMessage.includes('ticket')) {
                requestBody = { action: 'start_booking' };
            }
            // Check for availability
            else if (lowerMessage.includes('availability') || lowerMessage.includes('available') || lowerMessage.includes('check')) {
                const dateMatch = userText.match(/(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|today|tomorrow)/i);
                if (dateMatch) {
                    requestBody = {
                        action: 'check_availability',
                        date: dateMatch[1].toLowerCase()
                    };
                }
            }
            
            const response = await fetch('/chatbot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            const data = await response.json();
            
            typingIndicator.remove();
            appendMessageWithButtons(data.response, 'bot', data.buttons, data);
            
            // Handle special actions
            if (data.requires_login) {
                setTimeout(() => {
                    appendMessageWithButtons('🔗 Please log in to continue.', 'bot', data.buttons || [
                        {text: "🔗 Log In", action: "login", url: "/login"}
                    ]);
                }, 500);
            }
        } catch (error) {
            console.error('Error:', error);
            typingIndicator.remove();
            appendMessage('Sorry, I encountered an error. Please try again later.', 'bot error');
        }
    });
}
