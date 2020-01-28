class TagObject:
    """Represents a concept found by ConText in a document.
    Is the result of ConTextItem matching a span of text in a Doc.
    """

    def __init__(self, context_item, start, end, doc):
        """Create a new TagObject from a document span.

        context_item (int): The ConTextItem object which defines the modifier.
        start (int): The start token index.
        end (int): The end token index (non-inclusive).
        doc (Doc): The spaCy Doc which contains this span.
        """
        self.context_item = context_item
        self.start = start
        self.end = end
        self.doc = doc

        self._targets = []
        self._num_targets = 0

        self._scope_start = None
        self._scope_end = None

        self.set_scope()

    @property
    def span(self):
        """The spaCy Span object, which is a view of self.doc, covered by this match."""
        return self.doc[self.start: self.end]

    @property
    def rule(self):
        return self.context_item.rule

    @property
    def category(self):
        return self.context_item.category

    @property
    def scope(self):
        return self.doc[self._scope_start: self._scope_end]

    @property
    def allowed_types(self):
        return self.context_item.allowed_types

    @property
    def excluded_types(self):
        return self.context_item.excluded_types

    @property
    def num_targets(self):
        return self._num_targets

    @property
    def max_targets(self):
        return self.context_item.max_targets

    @property
    def max_scope(self):
        return self.context_item.max_scope

    def allows(self, target_label):
        """Returns True if a modifier is able to modify a target type.
        A modifier may not be allowed if either self.allowed_types is not None and
        target_label is not in it, or if self.excluded_types is not None and
        target_label is in it.
        """
        if self.allowed_types is not None:
            if target_label not in self.allowed_types:
                return False
            else:
                return True
        if self.excluded_types is not None:
            if target_label not in self.excluded_types:
                return True
            else:
                return False
        return True


    def set_scope(self):
        """Applies the rule of the ConTextItem which generated
        this TagObject to define a scope.
        If self.max_scope is None, then the default scope is the sentence which it occurs in
        in whichever direction defined by self.rule.
        For example, if the rule is "forward", the scope will be [self.end: sentence.end].
        If the rule is "backward", it will be [self.start: sentence.start].

        If self.max_scope is not None and the length of the default scope is longer than self.max_scope,
        it will be reduced to self.max_scope.


        """
        sent = self.doc[self.start].sent
        if sent is None:
            raise ValueError("ConText failed because sentence boundaries have not been set. "
                             "Add an upstream component such as the dependency parser, Sentencizer, or PyRuSH to detect sentence boundaries.")

        if self.rule.lower() == "forward":
            self._scope_start, self._scope_end = self.end, sent.end
            if self.max_scope is not None and (self._scope_end - self._scope_start) > self.max_scope:
                self._scope_end = self.end + self.max_scope


        elif self.rule.lower() == "backward":
            self._scope_start, self._scope_end = sent.start, self.start
            if self.max_scope is not None and (self._scope_end - self._scope_start) > self.max_scope:
                self._scope_start = self.start - self.max_scope
        else: # bidirectional
            self._scope_start, self._scope_end = sent.start, sent.end

            # Set the max scope on either side
            # Backwards
            if self.max_scope is not None and (self.start - self._scope_start) > self.max_scope:
                self._scope_start = self.start - self.max_scope
            # Forwards
            if self.max_scope is not None and (self._scope_end - self.end) > self.max_scope:
                self._scope_end = self.end + self.max_scope

    def update_scope(self, span):
        """Change the scope of self to be the given spaCy span.

        span (Span): a spaCy Span which contains the scope
        which a modifier should cover.
        """
        self._scope_start, self._scope_end = span.start, span.end

    def limit_scope(self, other):
        """If self and obj have the same category
        or if obj has a directionality of 'terminate',
        use the span of obj to update the scope of self.

        other (TagObject)
        Returns True if obj modfified the scope of self
        """
        if self.span.sent != other.span.sent:
            return False
        if self.rule.lower() == "terminate":
            return False
        if (other.rule.lower() != "terminate") and (other.category.lower() != self.category.lower()):
            return False

        orig_scope = self.scope

        if (self.rule.lower() in ("forward", "bidirectional")):
            if other > self:
                self._scope_end = min(self._scope_end, other.start)
        elif (self.rule.lower() in ("backward", "bidirectional")):
            if other < self:
                self._scope_start = max(self._scope_start, other.end)
        if orig_scope != self.scope:
            return True
        else:
            return False

    def modifies(self, target):
        """Returns True if the target is within the modifier scope
        and self is allowed to modify target.

        target (Span): a spaCy span representing a target concept.
        """
        if self.rule == "TERMINATE":
            return False
        if not self.allows(target.label_.upper()):
            return False
        if target[0] in self.scope:
            return True
        if target[-1] in self.scope:
            return True
        return False

    def modify(self, target):
        """Add target to the list of self._targets and increment self._num_targets."""
        self._targets.append(target)
        self._num_targets += 1

    def reduce_targets(self):
        """If self.max_targets is not None, reduce the targets which are modified
        so that only the n closest targets are left. Distance is measured as
        the distance to either the start or end of a target (whichever is closer).
        """
        if self.max_targets is None or self.num_targets <= self.max_targets:
            return

        target_dists = []
        for target in self._targets:
            dist = min(abs(self.start - target.end), abs(target.start - self.end))
            target_dists.append((target, dist))
        srtd_targets, _ = zip(*sorted(target_dists, key=lambda x: x[1]))
        self._targets = srtd_targets[:self.max_targets]
        self._num_targets = len(self._targets)

    def overlaps(self, other):
        if self.span[0] in other.span:
            return True
        if self.span[-1] in other.span:
            return True
        if other.span[0] in self.span:
            return True
        if other.span[-1] in self.span:
            return True
        return False

    def __gt__(self, other):
        return self.span > other.span

    def __ge__(self, other):
        return self.span >= other.span

    def __lt__(self, other):
        return self.span < other.span

    def __le__(self, other):
        return self.span <= other.span

    def __len__(self):
        return len(self.span)

    def __repr__(self):
        return f"<TagObject> [{self.span}, {self.category}]"