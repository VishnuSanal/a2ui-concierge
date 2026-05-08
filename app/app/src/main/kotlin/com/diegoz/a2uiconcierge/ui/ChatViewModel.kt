package com.diegoz.a2uiconcierge.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.diegoz.a2uiconcierge.chat.AgentEvent
import com.diegoz.a2uiconcierge.chat.ChatRepository
import com.diegoz.a2uiconcierge.chat.Message
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

class ChatViewModel(private val repo: ChatRepository) : ViewModel() {

    private val _messages = MutableStateFlow<List<Message>>(emptyList())
    val messages: StateFlow<List<Message>> = _messages.asStateFlow()

    fun onA2uiAction(json: String) {
        val summary = "[ui-action] $json"
        send(summary)
    }

    fun send(text: String) {
        if (text.isBlank()) return
        _messages.update { it + Message.User(UUID.randomUUID().toString(), text) }

        viewModelScope.launch {
            var textBubbleId: String? = null
            var a2uiBubbleId: String? = null

            repo.send(text).collect { ev ->
                when (ev) {
                    is AgentEvent.Text -> {
                        if (textBubbleId == null) {
                            val id = UUID.randomUUID().toString()
                            textBubbleId = id
                            _messages.update { it + Message.AgentText(id, ev.text) }
                        } else {
                            _messages.update { list ->
                                list.map { m ->
                                    if (m is Message.AgentText && m.id == textBubbleId) {
                                        m.copy(markdown = m.markdown + ev.text)
                                    } else m
                                }
                            }
                        }
                    }
                    is AgentEvent.A2ui -> {
                        if (a2uiBubbleId == null) {
                            val id = UUID.randomUUID().toString()
                            a2uiBubbleId = id
                            _messages.update { it + Message.AgentA2ui(id, listOf(ev.payload)) }
                        } else {
                            _messages.update { list ->
                                list.map { m ->
                                    if (m is Message.AgentA2ui && m.id == a2uiBubbleId) {
                                        m.copy(fragments = m.fragments + ev.payload)
                                    } else m
                                }
                            }
                        }
                    }
                    AgentEvent.End -> Unit
                }
            }
        }
    }
}
