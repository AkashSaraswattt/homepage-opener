"""Vercel entry point for the shared drafting handler."""

from app import AppHandler


class handler(AppHandler):
    def do_POST(self):
        self.handle_draft()
