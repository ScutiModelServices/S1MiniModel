from sentences import SentenceBuffer, chunks, cut


def test_cut_keeps_the_whitespace_and_the_unfinished_rest():
    assert cut("One. Two! Thr") == (["One. ", "Two! "], "Thr")
    assert cut("a\nb") == (["a\n"], "b")
    assert cut("3.5 is fine") == ([], "3.5 is fine")


def test_buffer_waits_for_the_whitespace_after_the_end():
    buffer = SentenceBuffer()
    assert [buffer.feed(p) for p in ["Hel", "lo.", " Wor", "ld."]] == [[], [], ["Hello. "], []]
    assert buffer.flush() == "World." and buffer.flush() == ""


def test_chunks_join_back_and_keep_a_long_sentence_whole():
    text = "one two. three four. five six seven eight nine"
    parts = chunks(text, lambda t: len(t.split()), 4)
    assert "".join(parts) == text and parts == ["one two. three four. ", "five six seven eight nine"]
    assert chunks("", len, 4) == []
