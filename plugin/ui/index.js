function notesPlugin() {
    return {
        notes: [],
        filter: 'All',
        search: '',
        selectedNote: null,
        noteContent: '',
        viewMode: 'grid',
        treeData: [],
        expandedFolders: {},
        graphData: { nodes: [], edges: [] },
        _network: null,
        _searchTimer: null,
        mobileFilterOpen: false,

        async init() {
            await this.loadVaultNotes();
            await Promise.all([this.loadTree(), this.loadGraph()]);
            AM.onCleanup(() => {
                if (this._network) {
                    this._network.destroy();
                    this._network = null;
                }
            });
        },

        async loadVaultNotes() {
            try {
                const params = [];
                if (this.filter !== 'All') params.push('folder=' + encodeURIComponent(this.filter));
                if (this.search) params.push('search=' + encodeURIComponent(this.search));
                const qs = params.length ? '?' + params.join('&') : '';
                const resp = await AM.fetch('/plugins/notes' + qs);
                if (resp) this.notes = await resp.json();
            } catch (e) { console.error('Notes loadVaultNotes', e); }
        },

        async loadTree() {
            try {
                const resp = await AM.fetch('/plugins/notes/tree');
                if (resp) {
                    this.treeData = await resp.json();
                    const expanded = {};
                    this.treeData.forEach(f => { expanded[f.name] = true; });
                    this.expandedFolders = expanded;
                }
            } catch (e) { console.error('Notes loadTree', e); }
        },

        async loadGraph() {
            try {
                const resp = await AM.fetch('/plugins/notes/graph');
                if (resp) this.graphData = await resp.json();
            } catch (e) { console.error('Notes loadGraph', e); }
        },

        switchView(mode) {
            this.viewMode = mode;
            if (mode === 'graph') {
                this.$nextTick(() => this._renderGraph());
            }
        },

        toggleFolder(name) {
            this.expandedFolders[name] = !this.expandedFolders[name];
        },

        searchVault() {
            if (this._searchTimer) clearTimeout(this._searchTimer);
            this._searchTimer = setTimeout(() => this.loadVaultNotes(), 300);
        },

        filteredNotes() {
            return this.notes;
        },

        async openNote(note) {
            try {
                const resp = await AM.fetch('/plugins/notes/' + encodeURIComponent(note.path));
                if (resp) {
                    const data = await resp.json();
                    this.selectedNote = note;
                    this.noteContent = data.content;
                }
            } catch (e) {
                AM.toast('Could not read note', 'error');
            }
        },

        closeNote() {
            this.selectedNote = null;
            this.noteContent = '';
        },

        async _loadVisNetwork() {
            if (window.vis && window.vis.Network) return window.vis;
            return new Promise((resolve, reject) => {
                const existing = document.querySelector('script[data-vis-network]');
                if (existing) {
                    existing.addEventListener('load', () => resolve(window.vis));
                    existing.addEventListener('error', () => reject(new Error('Failed to load vis-network')));
                    return;
                }
                const script = document.createElement('script');
                script.src = 'https://unpkg.com/vis-network/standalone/umd/vis-network.min.js';
                script.setAttribute('data-vis-network', '');
                script.onload = () => resolve(window.vis);
                script.onerror = () => reject(new Error('Failed to load vis-network'));
                document.head.appendChild(script);
            });
        },

        async _renderGraph() {
            if (this._network) {
                this._network.destroy();
                this._network = null;
            }
            const container = document.getElementById('notes-graph-network');
            if (!container) return;
            if (!this.graphData.nodes || this.graphData.nodes.length === 0) return;

            try {
                const vis = await this._loadVisNetwork();
                const cs = getComputedStyle(document.documentElement);
                const accent = cs.getPropertyValue('--accent').trim() || '#c4b8e0';
                const warm = cs.getPropertyValue('--warm').trim() || '#f5cc89';
                const text = cs.getPropertyValue('--text').trim() || '#ebe4da';
                const muted = cs.getPropertyValue('--muted').trim() || '#948fa8';
                const border = cs.getPropertyValue('--border').trim() || 'rgba(196,184,224,0.15)';

                const folderColors = {
                    'Diary': accent,
                    'Stories': warm,
                    'Projects': '#7ec8a0',
                    'People': '#e0a0b0',
                    'Notes': '#80b8d0',
                    'Inbox': muted,
                };

                const nodes = this.graphData.nodes.map(n => ({
                    id: n.id,
                    label: n.label,
                    color: {
                        background: folderColors[n.folder] || accent,
                        border: folderColors[n.folder] || accent,
                        highlight: { background: folderColors[n.folder] || accent, border: warm },
                    },
                }));
                const edges = this.graphData.edges.map(e => ({
                    from: e.from,
                    to: e.to,
                }));

                const data = {
                    nodes: new vis.DataSet(nodes),
                    edges: new vis.DataSet(edges),
                };
                const options = {
                    nodes: {
                        shape: 'dot',
                        size: 12,
                        font: { color: text, size: 12, face: 'sans-serif' },
                        borderWidth: 2,
                    },
                    edges: {
                        color: { color: border, highlight: accent },
                        arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                        smooth: { type: 'continuous' },
                    },
                    physics: {
                        stabilization: { iterations: 100 },
                        barnesHut: { gravitationalConstant: -3000 },
                    },
                    interaction: { hover: true, tooltipDelay: 200 },
                };

                this._network = new vis.Network(container, data, options);
                this._network.on('click', (params) => {
                    if (params.nodes.length > 0) {
                        this.openNote({ path: params.nodes[0] });
                    }
                });
            } catch (e) {
                AM.toast('Could not load graph visualization', 'error');
            }
        },
    };
}
