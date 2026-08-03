import asyncio

from app import broadcast


def test_publish_delivers_to_subscribed_queue():
    async def run():
        queue = broadcast.subscribe()
        await broadcast.publish({"status": "ok"})
        assert queue.get_nowait() == {"status": "ok"}
        broadcast.unsubscribe(queue)

    asyncio.run(run())


def test_unsubscribe_stops_delivery():
    async def run():
        queue = broadcast.subscribe()
        broadcast.unsubscribe(queue)
        await broadcast.publish({"status": "ok"})
        assert queue.empty()

    asyncio.run(run())


def test_publish_delivers_to_multiple_subscribers():
    async def run():
        first = broadcast.subscribe()
        second = broadcast.subscribe()
        await broadcast.publish({"status": "ok"})
        assert first.get_nowait() == {"status": "ok"}
        assert second.get_nowait() == {"status": "ok"}
        broadcast.unsubscribe(first)
        broadcast.unsubscribe(second)

    asyncio.run(run())
