package com.diegoz.a2uiconcierge.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import com.diegoz.a2uiconcierge.chat.Message

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(vm: ChatViewModel) {
    val messages by vm.messages.collectAsState()
    val thinking by vm.isThinking.collectAsState()
    val listState = rememberLazyListState()

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size - 1)
    }

    val haptic = LocalHapticFeedback.current
    LaunchedEffect(messages.size) {
        val last = messages.lastOrNull()
        if (last is Message.AgentA2ui && last.fragments.lastOrNull()?.get("component")?.toString()
                ?.contains("confirmation-card") == true) {
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Lumen Concierge") }) },
        bottomBar = { InputRow(onSend = vm::send) },
    ) { padding ->
        LazyColumn(
            state = listState,
            modifier = Modifier.padding(padding).fillMaxSize(),
        ) {
            items(messages, key = { it.id }) { m ->
                AnimatedVisibility(
                    visible = true,
                    enter = fadeIn() +
                            slideInVertically(initialOffsetY = { it / 4 }),
                ) {
                    when (m) {
                        is Message.User -> UserBubble(m.text)
                        is Message.AgentText -> AgentTextBubble(m.markdown)
                        is Message.AgentA2ui -> AgentA2uiBubble(
                            fragments = m.fragments,
                            onAction = vm::onA2uiAction,
                        )
                    }
                }
            }
            if (thinking) {
                item(key = "thinking") {
                    ThinkingDots()
                }
            }
        }
    }
}
