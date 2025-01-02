"""
Regular expressions and patterns used for content cleaning.
"""

import re

# Compile regex patterns for efficiency
HIDDEN_STYLE_PATTERN = re.compile(
    r'display:\s*none|'
    r'visibility:\s*hidden|'
    r'opacity:\s*0|'
    r'height:\s*0|'
    r'width:\s*0|'
    r'position:\s*absolute.*?(?:left|top):\s*-\d+'
)

CLUTTER_CLASS_PATTERN = re.compile(
    'advertisement|'
    'social-share|'
    'related|'
    'recommended|'
    'newsletter|'
    'subscription|'
    'popup|'
    'modal|'
    'overlay|'
    'cookie|'
    'banner|'
    'alert|'
    'notification|'
    'sidebar|'
    'widget|'
    'promo|'
    'sponsored|'
    'outbrain|'
    'taboola|'
    'disqus|'
    'comments?',
    re.I
)

JS_ERROR_PATTERN = re.compile(
    "(?:JavaScript|JS).*?(?:required|needed|enable|disabled)",
    re.I
)

# Element sets
HIDDEN_CLASSES = {
    'hidden', 'hide', 'invisible', 'd-none', 'display-none',
    'visually-hidden', 'sr-only', 'collapse', 'collapsed',
    'none', 'hidden-xs', 'hidden-sm', 'hidden-md', 'hidden-lg',
    'visuallyhidden', 'is-hidden', 'u-hidden'
}

UNWANTED_ELEMENTS = {
    'nav', 'header', 'footer', 'sidebar', 'menu', 'aside',
    'script', 'style', 'noscript', 'iframe', 'canvas',
    'ads', 'ad', 'advertisement', 'social-media', 'share-buttons',
    'comments', 'disqus', 'comment-section', 'discuss',
    'cookie-banner', 'popup', 'modal', 'overlay', 'dialog',
    'newsletter-form', 'subscription-form', 'paywall',
    'breadcrumb', 'pagination', 'search', 'tags', 'categories',
    'related-articles', 'recommended-posts', 'trending',
    'analytics', 'tracking', 'metrics', 'pixel'
}

CLUTTER_CLASSES = {
    'advertisement', 'social-share', 'related-posts', 'recommended',
    'newsletter', 'subscription', 'popup', 'modal', 'overlay',
    'cookie-notice', 'banner', 'alert', 'notification', 'widget',
    'sidebar', 'promo', 'sponsored', 'outbrain', 'taboola',
    'share-buttons', 'social-buttons', 'follow-buttons',
    'comments-area', 'disqus_thread', 'fb-comments',
    'newsletter-signup', 'subscription-form', 'paywall-container',
    'trending', 'popular', 'most-read', 'top-stories',
    'advertisement-region', 'dfp-ad', 'ad-unit', 'ad-slot'
}

CONTENT_CLASSES = {
    'content', 'article', 'post', 'text', 'entry', 'story',
    'main-content', 'article-content', 'post-content',
    'entry-content', 'story-content', 'article-body',
    'post-body', 'entry-body', 'story-body', 'main-text',
    'article-text', 'post-text'
} 