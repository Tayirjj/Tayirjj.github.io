import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:audioplayers/audioplayers.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../services/auth_service.dart';
import 'package:permission_handler/permission_handler.dart';

class SongsPage extends StatefulWidget {
  const SongsPage({super.key});

  @override
  State<SongsPage> createState() => _SongsPageState();
}

class _SongsPageState extends State<SongsPage> with TickerProviderStateMixin {
  // ─── Constants ────────────────────────────────────────────
  static const String BACKEND_API_URL = 'http://192.168.70.73:3000';

  // ─── Services ─────────────────────────────────────────────
  final AuthService _authService = AuthService();
  final AudioPlayer _audioPlayer = AudioPlayer();

  // ─── State ────────────────────────────────────────────────
  bool isInstrumental = false;
  String selectedMode = 'Quick Mode';
  bool _isGenerating = false;
  bool _isPlaying = false;
  Uint8List? _generatedAudioBytes;
  String? _errorMessage;
  Duration _audioDuration = Duration.zero;
  Duration _audioPosition = Duration.zero;

  // ─── Quick Mode Controllers ────────────────────────────────
  final TextEditingController _quickDescController = TextEditingController();

  // ─── Custom Mode Controllers ──────────────────────────────
  final TextEditingController _styleController = TextEditingController();
  final TextEditingController _lyricsController = TextEditingController();
  final TextEditingController _titleController = TextEditingController();
  String _selectedVocal = 'Auto';
  String _selectedStyle = '';
  String _selectedGenre = '';
  String _selectedTopic = '';
  String _selectedMood = '';

  // ─── Explore Songs State ──────────────────────────────────
  List<Map<String, dynamic>> _exploreSongs = [];
  bool _isLoadingExploreSongs = true;
  // ─── Vertical List Songs State ────────────────────────────
  List<Map<String, dynamic>> _verticalSongs = [];
  bool _isLoadingVerticalSongs = true;

  // ─── Mini Player State ────────────────────────────────────
  Map<String, dynamic>? _currentPlayingSong;
  final AudioPlayer _exploreSongPlayer = AudioPlayer();
  bool _isExplorePlayerPlaying = false;
  String? _playingExploreSongId;
  String _playingSource = '';
  bool _isMiniPlayerExpanded = false;
  bool _isShowingLyrics = false;
  String _currentLyrics = '';
  bool _isLoadingLyrics = false;
  Duration _exploreSongDuration = Duration.zero;
  Duration _exploreSongPosition = Duration.zero;

  // ─── Options ──────────────────────────────────────────────
  final List<String> _moods = ['Sad', 'Energetic', 'Romantic', 'Happy', 'Calm', 'Angry'];
  final List<String> _genres = ['Pop', 'Rap', 'Classic', 'Rock', 'Jazz', 'Electronic'];
  final List<String> _topics = ['Love', 'War', 'Homeland', 'Future', 'Friendship', 'Freedom'];
  final List<String> _styleTags = ['brass', 'trap', 'punk', 'easy listening', 'acoustic', 'orchestral'];

  @override
  void initState() {
    super.initState();
    _audioPlayer.onDurationChanged.listen((d) {
      if (mounted) setState(() => _audioDuration = d);
    });
    _audioPlayer.onPositionChanged.listen((p) {
      if (mounted) setState(() => _audioPosition = p);
    });
    _audioPlayer.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _isPlaying = false);
    });

    // ─── Explore Song Player Listeners ───────────────────────
    _exploreSongPlayer.onPlayerComplete.listen((_) {
      if (mounted) {
        setState(() {
          _isExplorePlayerPlaying = false;
        });
      }
    });
    _exploreSongPlayer.onDurationChanged.listen((d) {
      if (mounted) setState(() => _exploreSongDuration = d);
    });
    _exploreSongPlayer.onPositionChanged.listen((p) {
      if (mounted) setState(() => _exploreSongPosition = p);
    });

    _fetchExploreSongs();
    _fetchVerticalSongs();
  }

  @override
  void dispose() {
    _quickDescController.dispose();
    _styleController.dispose();
    _lyricsController.dispose();
    _titleController.dispose();
    _audioPlayer.dispose();
    _exploreSongPlayer.dispose();
    super.dispose();
  }


  // ─── Get Songs Folder ─────────────────────────────────────
Future<Directory> _getSongsFolder(String songName) async {
  final base = Directory('/storage/emulated/0/VoicesAI/songs/$songName');
  if (!await base.exists()) {
    await base.create(recursive: true);
  }
  return base;
}

// ─── Sync Songs Locally ───────────────────────────────────
Future<void> _syncSongsLocally(List<Map<String, dynamic>> songs) async {
  try {
    if (Platform.isAndroid) {
      final status = await Permission.manageExternalStorage.request();
      if (!status.isGranted) {
        await Permission.storage.request();
      }
    }

    for (final song in songs) {
      final songName = song['id'] as String;
      final photoUrl = song['photo'] as String;
      final musicUrl = song['music'] as String;

      final folder = await _getSongsFolder(songName);

      // ── تحميل الصورة ──
      if (photoUrl.isNotEmpty) {
        final photoFile = File('${folder.path}/photo.jpg');
        if (!await photoFile.exists()) {
          try {
            final response = await http.get(Uri.parse(photoUrl));
            if (response.statusCode == 200) {
              await photoFile.writeAsBytes(response.bodyBytes);
            }
          } catch (e) {
            debugPrint('Error downloading photo for $songName: $e');
          }
        }
      }

      // ── تحميل الموسيقى ──
      if (musicUrl.isNotEmpty) {
        final musicFile = File('${folder.path}/music.mp3');
        if (!await musicFile.exists()) {
          try {
            final response = await http.get(Uri.parse(musicUrl));
            if (response.statusCode == 200) {
              await musicFile.writeAsBytes(response.bodyBytes);
            }
          } catch (e) {
            debugPrint('Error downloading music for $songName: $e');
          }
        }
      }
    }
    debugPrint('✅ Songs sync completed');
  } catch (e) {
    debugPrint('Songs sync error: $e');
  }
}

// ─── Get Local Song Photo Path ────────────────────────────
String _getLocalPhotoPath(String songName) =>
    '/storage/emulated/0/VoicesAI/songs/$songName/photo.jpg';

// ─── Get Local Song Music Path ────────────────────────────
String _getLocalMusicPath(String songName) =>
    '/storage/emulated/0/VoicesAI/songs/$songName/music.mp3';


  // ─── Fetch Explore Songs from Firestore ───────────────────
  Future<void> _fetchExploreSongs() async {
    try {
      final snapshot = await FirebaseFirestore.instance
          .collection('explore songs')
          .get();

      final songs = snapshot.docs.map((doc) {
        final data = doc.data();
        return {
          'id': doc.id,
          'title': doc.id,
          'description': data['discription'] ?? '',
          'lyrics': data['lyrics'] ?? '',
          'music': data['music'] ?? '',
          'photo': data['photo'] ?? '',
          'order': int.tryParse(data['order']?.toString() ?? '0') ?? 0,
        };
      }).toList();

      songs.sort((a, b) => (a['order'] as int).compareTo(b['order'] as int));

      if (mounted) {
        setState(() {
          _exploreSongs = songs;
          _isLoadingExploreSongs = false;
        });
      }

      // ── مزامنة محلية في الخلفية ──
      _syncSongsLocally(songs);

    } catch (e) {
      if (mounted) setState(() => _isLoadingExploreSongs = false);
    }
  }

  // ─── Get Vertical Songs Folder ────────────────────────────
  String _getLocalVerticalPhotoPath(String songName) =>
      '/storage/emulated/0/VoicesAI/vertical_songs/$songName/photo.jpg';

  String _getLocalVerticalMusicPath(String songName) =>
      '/storage/emulated/0/VoicesAI/vertical_songs/$songName/music.mp3';

  // ─── Sync Vertical Songs Locally ─────────────────────────
  Future<void> _syncVerticalSongsLocally(List<Map<String, dynamic>> songs) async {
    try {
      if (Platform.isAndroid) {
        final status = await Permission.manageExternalStorage.request();
        if (!status.isGranted) await Permission.storage.request();
      }

      for (final song in songs) {
        final songName = song['id'] as String;
        final photoUrl = song['photo'] as String;
        final musicUrl = song['music'] as String;

        final folder = Directory('/storage/emulated/0/VoicesAI/vertical_songs/$songName');
        if (!await folder.exists()) await folder.create(recursive: true);

        if (photoUrl.isNotEmpty) {
          final photoFile = File('${folder.path}/photo.jpg');
          if (!await photoFile.exists()) {
            try {
              final response = await http.get(Uri.parse(photoUrl));
              if (response.statusCode == 200) await photoFile.writeAsBytes(response.bodyBytes);
            } catch (e) { debugPrint('Error photo $songName: $e'); }
          }
        }

        if (musicUrl.isNotEmpty) {
          final musicFile = File('${folder.path}/music.mp3');
          if (!await musicFile.exists()) {
            try {
              final response = await http.get(Uri.parse(musicUrl));
              if (response.statusCode == 200) await musicFile.writeAsBytes(response.bodyBytes);
            } catch (e) { debugPrint('Error music $songName: $e'); }
          }
        }
      }
      debugPrint('✅ Vertical songs sync completed');
    } catch (e) {
      debugPrint('Vertical sync error: $e');
    }
  }

  // ─── Fetch Vertical List Songs ────────────────────────────
  Future<void> _fetchVerticalSongs() async {
    try {
      final snapshot = await FirebaseFirestore.instance
          .collection('Vertical list songs')
          .get();

      final songs = snapshot.docs.map((doc) {
        final data = doc.data();
        return {
          'id': doc.id,
          'title': doc.id,
          'description': data['discription'] ?? '',
          'lyrics': data['lyrics'] ?? '',
          'music': data['music'] ?? '',
          'photo': data['photo'] ?? '',
          'order': int.tryParse(data['order']?.toString() ?? '0') ?? 0,
        };
      }).toList();

      songs.sort((a, b) => (a['order'] as int).compareTo(b['order'] as int));

      if (mounted) {
        setState(() {
          _verticalSongs = songs;
          _isLoadingVerticalSongs = false;
        });
      }

      _syncVerticalSongsLocally(songs);
    } catch (e) {
      if (mounted) setState(() => _isLoadingVerticalSongs = false);
    }
  }

  // ─── Play Song (opens mini player) ───────────────────────
  Future<void> _playSong(Map<String, dynamic> song) async {
    final songId = song['id'] as String;
    final musicUrl = song['music'] as String;

    if (musicUrl.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('لا يوجد رابط صوتي لهذه الأغنية')),
      );
      return;
    }

    if (_playingExploreSongId == songId && _isExplorePlayerPlaying) {
      await _exploreSongPlayer.pause();
      setState(() => _isExplorePlayerPlaying = false);
      return;
    }

    try {
      await _exploreSongPlayer.stop();
      setState(() {
        _playingExploreSongId = songId;
        _playingSource = 'explore';
        _isExplorePlayerPlaying = false;
        _currentPlayingSong = song;
        _isShowingLyrics = false;
        _currentLyrics = '';
        _exploreSongDuration = Duration.zero;
        _exploreSongPosition = Duration.zero;
      });

      final localMusic = File(_getLocalMusicPath(songId));
      if (await localMusic.exists()) {
        await _exploreSongPlayer.setSourceDeviceFile(localMusic.path);
      } else {
        await _exploreSongPlayer.setSourceUrl(musicUrl);
      }
      await _exploreSongPlayer.resume();
      setState(() => _isExplorePlayerPlaying = true);

    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('خطأ في تشغيل الأغنية: $e')),
      );
    }
  }

  // ─── Toggle Explore Song Playback ─────────────────────────
  Future<void> _toggleExploreSong(String songId, String musicUrl) async {
    final song = _exploreSongs.firstWhere((s) => s['id'] == songId, orElse: () => {});
    if (song.isNotEmpty) {
      await _playSong(song);
    }
  }

  // ─── Load Lyrics from Firestore ───────────────────────────
  Future<void> _loadLyrics(String songId) async {
    setState(() => _isLoadingLyrics = true);
    try {
      final doc = await FirebaseFirestore.instance
          .collection('explore songs')
          .doc(songId)
          .get();
      if (doc.exists) {
        final lyrics = doc.data()?['lyrics'] ?? '';
        setState(() {
          _currentLyrics = lyrics;
          _isShowingLyrics = true;
          _isLoadingLyrics = false;
        });
      } else {
        setState(() {
          _currentLyrics = 'لا توجد كلمات لهذه الأغنية';
          _isShowingLyrics = true;
          _isLoadingLyrics = false;
        });
      }
    } catch (e) {
      setState(() {
        _currentLyrics = 'حدث خطأ في تحميل الكلمات';
        _isShowingLyrics = true;
        _isLoadingLyrics = false;
      });
    }
  }

  // ─── Download Song ─────────────────────────────────────────
  Future<void> _downloadSong(String musicUrl, String title) async {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('جاري تحميل "$title"...'),
        backgroundColor: const Color(0xFF1A1F3A),
      ),
    );
    // TODO: implement actual download logic
  }

  // ─── API Call ─────────────────────────────────────────────
  Future<void> _generateSong({
    required String lyrics,
    required String style,
    required String genre,
    required String topic,
    required String outputType,
    int duration = 15,
  }) async {
    setState(() {
      _isGenerating = true;
      _errorMessage = null;
      _generatedAudioBytes = null;
    });

    try {
      final user = _authService.currentUser;
      final idToken = await user?.getIdToken();

      final response = await http.post(
        Uri.parse('$BACKEND_API_URL/song/generate'),
        headers: {
          'Authorization': 'Bearer $idToken',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'lyrics': lyrics,
          'style': style,
          'genre': genre,
          'topic': topic,
          'output_type': outputType,
          'duration': duration,
        }),
      );

      if (response.statusCode == 200) {
        setState(() {
          _generatedAudioBytes = response.bodyBytes;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('🎵 تم توليد الأغنية بنجاح!'),
            backgroundColor: Colors.green,
          ),
        );
      } else {
        final error = jsonDecode(response.body);
        setState(() => _errorMessage = error['error'] ?? 'حدث خطأ غير معروف');
      }
    } catch (e) {
      setState(() => _errorMessage = e.toString());
    } finally {
      setState(() => _isGenerating = false);
    }
  }

  void _onQuickModeCreate() {
    if (_quickDescController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('الرجاء كتابة وصف للأغنية')),
      );
      return;
    }
    _generateSong(
      lyrics: isInstrumental ? '' : _quickDescController.text,
      style: 'general',
      genre: 'pop',
      topic: 'general',
      outputType: isInstrumental ? 'music_only' : 'full_song',
    );
  }

  void _onCustomModeCreate() {
    if (!isInstrumental && _lyricsController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Please enter lyrics')),
      );
      return;
    }

    final data = {
      "lyrics": isInstrumental ? "" : _lyricsController.text,
      "outputType": isInstrumental ? "music_only" : "full_song",
      "mood": _selectedMood,
      "genre": _selectedGenre,
      "topic": _selectedTopic,
    };

    print(data);
  }

  // ─── Audio Player (generated) ─────────────────────────────
  Future<void> _togglePlay() async {
    if (_generatedAudioBytes == null) return;

    if (_isPlaying) {
      await _audioPlayer.pause();
      setState(() => _isPlaying = false);
    } else {
      await _audioPlayer.play(BytesSource(_generatedAudioBytes!));
      setState(() => _isPlaying = true);
    }
  }

  String _formatDuration(Duration d) {
    final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  // ─── Build ────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        // ── Main Scrollable Content ──
        SingleChildScrollView(
          child: Padding(
            padding: EdgeInsets.fromLTRB(12, 12, 12, _currentPlayingSong != null ? 80 : 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Main Card ──
                Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A1F3A),
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(24),
                      topRight: Radius.circular(24),
                    ),
                  ),
                  child: Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            TextField(
                              controller: _quickDescController,
                              maxLines: null,
                              style: const TextStyle(color: Colors.white, fontSize: 16),
                              decoration: InputDecoration(
                                hintText: 'صف الأغنية التي تريد إنشاءها...',
                                hintStyle: TextStyle(color: Colors.grey[500], fontSize: 15),
                                border: InputBorder.none,
                              ),
                            ),
                            const SizedBox(height: 25),
                            Row(
                              children: [
                                GestureDetector(
                                  onTap: () => setState(() => isInstrumental = !isInstrumental),
                                  child: Container(
                                    width: 40,
                                    height: 20,
                                    decoration: BoxDecoration(
                                      color: isInstrumental ? Colors.white : Colors.grey[700],
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: AnimatedAlign(
                                      duration: const Duration(milliseconds: 200),
                                      alignment: isInstrumental ? Alignment.centerLeft : Alignment.centerRight,
                                      child: Container(
                                        width: 20,
                                        height: 20,
                                        margin: const EdgeInsets.all(2),
                                        decoration: BoxDecoration(
                                          color: isInstrumental ? const Color(0xFF1A1F3A) : Colors.white,
                                          shape: BoxShape.circle,
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                const Text('Instrumental', style: TextStyle(color: Colors.white, fontSize: 14)),
                                const Spacer(),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF2A2F4A),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Row(
                                    children: const [
                                      Icon(Icons.diamond, color: Color(0xFFFF6B9D), size: 15),
                                      SizedBox(width: 6),
                                      Text('600', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.all(5),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF2A2F4A),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: const Icon(Icons.auto_fix_high, color: Colors.white, size: 20),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      Container(
                        color: const Color(0xFF0B0E27),
                        child: Row(
                          children: [
                            _buildModeButton('Quick Mode'),
                            _buildModeButton('Custom Mode'),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 15),

                if (_errorMessage != null)
                  Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.red.withOpacity(0.4)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline, color: Colors.red, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _errorMessage!,
                            style: const TextStyle(color: Colors.red, fontSize: 13),
                          ),
                        ),
                      ],
                    ),
                  ),

                if (_generatedAudioBytes != null) _buildAudioPlayer(),

                const SizedBox(height: 4),

                // ── Create Song Button ──
                Container(
                  width: double.infinity,
                  height: 50,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFFFF6B9D), Color(0xFFC44569)],
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: _isGenerating ? null : _onQuickModeCreate,
                      borderRadius: BorderRadius.circular(16),
                      child: Center(
                        child: _isGenerating
                            ? const Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      color: Colors.white,
                                      strokeWidth: 2,
                                    ),
                                  ),
                                  SizedBox(width: 12),
                                  Text(
                                    'جاري التوليد...',
                                    style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                                  ),
                                ],
                              )
                            : const Text(
                                'Create Song',
                                style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                              ),
                      ),
                    ),
                  ),
                ),

                const SizedBox(height: 15),

                const Text(
                  'Explore Songs',
                  style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 16),

                // ── Explore Songs Horizontal List ──
                SizedBox(
                  height: 220,
                  child: _isLoadingExploreSongs
                      ? const Center(
                          child: CircularProgressIndicator(color: Color(0xFFFF6B9D)),
                        )
                      : _exploreSongs.isEmpty
                          ? Center(
                              child: Text(
                                'No Songs',
                                style: TextStyle(color: Colors.grey[400], fontSize: 14),
                              ),
                            )
                          : ListView.builder(
                              scrollDirection: Axis.horizontal,
                              itemCount: _exploreSongs.length,
                              itemBuilder: (context, index) {
                                final song = _exploreSongs[index];
                                final songId = song['id'] as String;
                                final isThisSongPlaying =
                                    _playingExploreSongId == songId && _isExplorePlayerPlaying && _playingSource == 'explore';

                                return Container(
                                  width: 120,
                                  margin: const EdgeInsets.only(right: 16),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      GestureDetector(
                                        onTap: () => _playSong(song),
                                        child: Stack(
                                          children: [
                                            Container(
                                              height: 160,
                                              decoration: BoxDecoration(
                                                color: const Color(0xFF1A1F3A),
                                                borderRadius: BorderRadius.circular(12),
                                              ),
                                              child: ClipRRect(
                                                borderRadius: BorderRadius.circular(12),
                                                child: (song['photo'] as String).isNotEmpty
                                                    ? FutureBuilder<bool>(
                                                        future: File(_getLocalPhotoPath(song['id'] as String)).exists(),
                                                        builder: (context, snapshot) {
                                                          if (snapshot.data == true) {
                                                            return Image.file(
                                                              File(_getLocalPhotoPath(song['id'] as String)),
                                                              width: double.infinity,
                                                              height: 160,
                                                              fit: BoxFit.cover,
                                                            );
                                                          }
                                                          return Image.network(
                                                            song['photo'] as String,
                                                            width: double.infinity,
                                                            height: 160,
                                                            fit: BoxFit.cover,
                                                            errorBuilder: (_, __, ___) => Center(
                                                              child: Icon(
                                                                Icons.music_note,
                                                                color: Colors.white.withOpacity(0.3),
                                                                size: 60,
                                                              ),
                                                            ),
                                                          );
                                                        },
                                                      )
                                                    : Center(
                                                        child: Icon(
                                                          Icons.music_note,
                                                          color: Colors.white.withOpacity(0.3),
                                                          size: 60,
                                                        ),
                                                      ),
                                                          ),
                                            ),
                                            if (isThisSongPlaying)
                                              Positioned.fill(
                                                child: Container(
                                                  decoration: BoxDecoration(
                                                    borderRadius: BorderRadius.circular(12),
                                                    color: Colors.black.withOpacity(0.4),
                                                  ),
                                                  child: Center(
                                                    child: Container(
                                                      width: 40,
                                                      height: 40,
                                                      decoration: BoxDecoration(
                                                        color: const Color(0xFFFF6B9D).withOpacity(0.9),
                                                        shape: BoxShape.circle,
                                                      ),
                                                      child: const Icon(
                                                        Icons.pause,
                                                        color: Colors.white,
                                                        size: 22,
                                                      ),
                                                    ),
                                                  ),
                                                ),
                                              ),
                                          ],
                                        ),
                                      ),
                                      const SizedBox(height: 8),
                                      Text(
                                        song['title'] as String,
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 14,
                                          fontWeight: FontWeight.w600,
                                        ),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        song['description'] as String,
                                        style: TextStyle(color: Colors.grey[400], fontSize: 12),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                ),

             

                // ── Song List ──
                

                const SizedBox(height: 15),

                // ── Vertical List Songs ──
                const Text(
                  'More Songs',
                  style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 16),

                _isLoadingVerticalSongs
                    ? const Center(child: CircularProgressIndicator(color: Color(0xFFFF6B9D)))
                    : _verticalSongs.isEmpty
                        ? Center(
                            child: Text('No Songs', style: TextStyle(color: Colors.grey[400], fontSize: 14)),
                          )
                        : Container(
                            decoration: BoxDecoration(
                              color: const Color(0xFF1A1F3A),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: Column(
                              children: _verticalSongs.asMap().entries.map((entry) {
                                final index = entry.key;
                                final song = entry.value;
                                final songId = song['id'] as String;
                                final isThisSongPlaying =
                                    _playingExploreSongId == songId && _isExplorePlayerPlaying;
                                final localPhoto = File(_getLocalVerticalPhotoPath(songId));

                                return Column(
                                  children: [
                                    GestureDetector(
                                      onTap: () async {
                                        final musicUrl = song['music'] as String;
                                        if (musicUrl.isEmpty) return;

                                        if (_playingExploreSongId == songId && _isExplorePlayerPlaying) {
                                          await _exploreSongPlayer.pause();
                                          setState(() => _isExplorePlayerPlaying = false);
                                          return;
                                        }

                                        try {
                                          await _exploreSongPlayer.stop();
                                          setState(() {
                                            _playingExploreSongId = songId;
                                            _playingSource = 'vertical';
                                            _isExplorePlayerPlaying = false;
                                            _currentPlayingSong = song;
                                            _isShowingLyrics = false;
                                            _currentLyrics = '';
                                            _exploreSongDuration = Duration.zero;
                                            _exploreSongPosition = Duration.zero;
                                          });
                                          final localMusic = File(_getLocalVerticalMusicPath(songId));
                                          if (await localMusic.exists()) {
                                            await _exploreSongPlayer.setSourceDeviceFile(localMusic.path);
                                          } else {
                                            await _exploreSongPlayer.setSourceUrl(musicUrl);
                                          }
                                          await _exploreSongPlayer.resume();
                                          setState(() => _isExplorePlayerPlaying = true);
                                        } catch (e) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            SnackBar(content: Text('خطأ: $e')),
                                          );
                                        }
                                      },
                                      child: Padding(
                                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                                        child: Row(
                                          children: [
                                            // ── صورة الأغنية ──
                                            ClipRRect(
                                              borderRadius: BorderRadius.circular(10),
                                              child: FutureBuilder<bool>(
                                                future: localPhoto.exists(),
                                                builder: (context, snapshot) {
                                                  if (snapshot.data == true) {
                                                    return Image.file(
                                                      localPhoto,
                                                      width: 60,
                                                      height: 60,
                                                      fit: BoxFit.cover,
                                                    );
                                                  }
                                                  final photoUrl = song['photo'] as String;
                                                  return photoUrl.isNotEmpty
                                                      ? Image.network(
                                                          photoUrl,
                                                          width: 60,
                                                          height: 60,
                                                          fit: BoxFit.cover,
                                                          errorBuilder: (_, __, ___) => Container(
                                                            width: 60,
                                                            height: 60,
                                                            color: const Color(0xFF2A2F4A),
                                                            child: const Icon(Icons.music_note, color: Colors.white54),
                                                          ),
                                                        )
                                                      : Container(
                                                          width: 60,
                                                          height: 60,
                                                          color: const Color(0xFF2A2F4A),
                                                          child: const Icon(Icons.music_note, color: Colors.white54),
                                                        );
                                                },
                                              ),
                                            ),
                                            const SizedBox(width: 12),
                                            // ── العنوان والوصف ──
                                            Expanded(
                                              child: Column(
                                                crossAxisAlignment: CrossAxisAlignment.start,
                                                children: [
                                                  Text(
                                                    song['title'] as String,
                                                    style: const TextStyle(
                                                      color: Colors.white,
                                                      fontSize: 15,
                                                      fontWeight: FontWeight.w600,
                                                    ),
                                                    maxLines: 1,
                                                    overflow: TextOverflow.ellipsis,
                                                  ),
                                                  const SizedBox(height: 3),
                                                  Text(
                                                    song['description'] as String,
                                                    style: TextStyle(color: Colors.grey[400], fontSize: 12),
                                                    maxLines: 1,
                                                    overflow: TextOverflow.ellipsis,
                                                  ),
                                                ],
                                              ),
                                            ),
                                            // ── زر التشغيل ──
                                            Icon(
                                              isThisSongPlaying ? Icons.pause_circle : Icons.play_circle_outline,
                                              color: isThisSongPlaying ? const Color(0xFFFF6B9D) : Colors.grey[400],
                                              size: 30,
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),
                                    if (index < _verticalSongs.length - 1)
                                      Divider(color: Colors.white.withOpacity(0.06), height: 1, indent: 84),
                                  ],
                                );
                              }).toList(),
                            ),
                          ),

                const SizedBox(height: 20),
              ],
            ),
          ),
        ),

        // ── Mini Player ──
        if (_currentPlayingSong != null)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: _buildMiniPlayer(),
          ),
      ],
    );
  }

  // ─── Mini Player Widget ───────────────────────────────────
  Widget _buildMiniPlayer() {
    final song = _currentPlayingSong!;
    final photoUrl = song['photo'] as String;
    final title = song['title'] as String;
    final description = song['description'] as String;
    final musicUrl = song['music'] as String;
    final songId = song['id'] as String;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
      height: _isMiniPlayerExpanded ? MediaQuery.of(context).size.height * 0.5 : 70,
      decoration: BoxDecoration(
        color: const Color(0xFF12152E),
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(16),
          topRight: Radius.circular(16),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.5),
            blurRadius: 20,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: _isMiniPlayerExpanded
          ? _buildExpandedPlayer(song, photoUrl, title, description, musicUrl, songId)
          : _buildCollapsedPlayer(photoUrl, title, description),
    );
  }

  // ─── Collapsed Mini Player ────────────────────────────────
  Widget _buildCollapsedPlayer(String photoUrl, String title, String description) {
    return GestureDetector(
      onTap: () => setState(() => _isMiniPlayerExpanded = true),
      child: Container(
        height: 70,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            // Song Cover
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: photoUrl.isNotEmpty
                  ? Image.network(
                      photoUrl,
                      width: 50,
                      height: 50,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        width: 50,
                        height: 50,
                        color: const Color(0xFF1A1F3A),
                        child: const Icon(Icons.music_note, color: Colors.white54),
                      ),
                    )
                  : Container(
                      width: 50,
                      height: 50,
                      color: const Color(0xFF1A1F3A),
                      child: const Icon(Icons.music_note, color: Colors.white54),
                    ),
            ),
            const SizedBox(width: 12),
            // Title & Description
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    description,
                    style: TextStyle(color: Colors.grey[400], fontSize: 12),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            // Play/Pause
            GestureDetector(
              onTap: () async {
                if (_isExplorePlayerPlaying) {
                  await _exploreSongPlayer.pause();
                  setState(() => _isExplorePlayerPlaying = false);
                } else {
                  await _exploreSongPlayer.resume();
                  setState(() => _isExplorePlayerPlaying = true);
                }
              },
              child: Container(
                width: 40,
                height: 40,
                decoration: const BoxDecoration(
                  color: Color(0xFF1A1F3A),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  _isExplorePlayerPlaying ? Icons.pause : Icons.play_arrow,
                  color: Colors.white,
                  size: 22,
                ),
              ),
            ),
            const SizedBox(width: 8),
            // Skip Next
            GestureDetector(
              onTap: () {},
              child: const Icon(Icons.skip_next, color: Colors.white, size: 28),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Expanded Player ─────────────────────────────────────
  Widget _buildExpandedPlayer(
    Map<String, dynamic> song,
    String photoUrl,
    String title,
    String description,
    String musicUrl,
    String songId,
  ) {
    return Column(
      children: [
        // ── Drag Handle ──
        Padding(
          padding: const EdgeInsets.only(top: 10, bottom: 6),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const SizedBox(width: 52),
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[600],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(right: 12),
                child: GestureDetector(
                  onTap: () => setState(() {
                    _isMiniPlayerExpanded = false;
                    _isShowingLyrics = false;
                  }),
                  child: Container(
                    width: 28,
                    height: 28,
                    decoration: const BoxDecoration(
                      color: Color(0xFF2A2F4A),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.close, color: Colors.white, size: 16),
                  ),
                ),
              ),
            ],
          ),
        ),

        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Column(
              children: [
                const SizedBox(height: 8),

                // ── Song Cover ──
                ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: photoUrl.isNotEmpty
                      ? Image.network(
                          photoUrl,
                          width: 110,
                          height: 110,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => Container(
                            width: 110,
                            height: 110,
                            color: const Color(0xFF1A1F3A),
                            child: const Icon(Icons.music_note, color: Colors.white54, size: 50),
                          ),
                        )
                      : Container(
                          width: 110,
                          height: 110,
                          color: const Color(0xFF1A1F3A),
                          child: const Icon(Icons.music_note, color: Colors.white54, size: 50),
                        ),
                ),

                const SizedBox(height: 12),

                // ── Title ──
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: TextStyle(color: Colors.grey[400], fontSize: 13),
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),

                const SizedBox(height: 12),

                // ── Lyrics Display ──
                if (_isShowingLyrics) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1A1F3A),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: _isLoadingLyrics
                        ? const Center(
                            child: CircularProgressIndicator(
                              color: Color(0xFFFF6B9D),
                              strokeWidth: 2,
                            ),
                          )
                        : Text(
                            _currentLyrics,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                              height: 1.7,
                            ),
                          ),
                  ),
                  const SizedBox(height: 12),
                ],

                // ── Progress Bar ──
                SliderTheme(
                  data: SliderTheme.of(context).copyWith(
                    activeTrackColor: Colors.white,
                    inactiveTrackColor: Colors.white24,
                    thumbColor: Colors.white,
                    thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 5),
                    overlayShape: SliderComponentShape.noOverlay,
                    trackHeight: 2.5,
                  ),
                  child: Slider(
                    value: _exploreSongDuration.inSeconds > 0
                        ? (_exploreSongPosition.inSeconds / _exploreSongDuration.inSeconds).clamp(0.0, 1.0)
                        : 0.0,
                    onChanged: (value) async {
                      final position = Duration(seconds: (value * _exploreSongDuration.inSeconds).round());
                      await _exploreSongPlayer.seek(position);
                    },
                  ),
                ),

                // ── Duration Row ──
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _formatDuration(_exploreSongPosition),
                        style: TextStyle(color: Colors.grey[400], fontSize: 11),
                      ),
                      Text(
                        _formatDuration(_exploreSongDuration),
                        style: TextStyle(color: Colors.grey[400], fontSize: 11),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 8),

                // ── Controls Row ──
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Skip Previous
                    GestureDetector(
                      onTap: () async {
                        await _exploreSongPlayer.seek(Duration.zero);
                      },
                      child: const Icon(Icons.skip_previous, color: Colors.white, size: 32),
                    ),
                    const SizedBox(width: 24),
                    // Play/Pause
                    GestureDetector(
                      onTap: () async {
                        if (_isExplorePlayerPlaying) {
                          await _exploreSongPlayer.pause();
                          setState(() => _isExplorePlayerPlaying = false);
                        } else {
                          await _exploreSongPlayer.resume();
                          setState(() => _isExplorePlayerPlaying = true);
                        }
                      },
                      child: Container(
                        width: 56,
                        height: 56,
                        decoration: const BoxDecoration(
                          color: Colors.white,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          _isExplorePlayerPlaying ? Icons.pause : Icons.play_arrow,
                          color: const Color(0xFF12152E),
                          size: 30,
                        ),
                      ),
                    ),
                    const SizedBox(width: 24),
                    // Skip Next
                    GestureDetector(
                      onTap: () {},
                      child: const Icon(Icons.skip_next, color: Colors.white, size: 32),
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // ── Action Buttons Row 1: Download, Share, Reuse, Regenerate ──
                // ── Action Buttons: Download, Share, Reuse, Show Lyrics ──
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildActionButton(
                        icon: Icons.download_outlined,
                        label: 'Download',
                        onTap: () => _downloadSong(musicUrl, title),
                      ),
                      const SizedBox(width: 10),
                      _buildActionButton(
                        icon: Icons.share_outlined,
                        label: 'Share',
                        onTap: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('جاري المشاركة...')),
                          );
                        },
                      ),
                      const SizedBox(width: 10),
                      _buildActionButton(
                        icon: Icons.repeat,
                        label: 'Reuse',
                        onTap: () {},
                      ),
                      const SizedBox(width: 10),
                      GestureDetector(
                        onTap: () {
                          if (_isShowingLyrics) {
                            setState(() => _isShowingLyrics = false);
                          } else {
                            _loadLyrics(songId);
                          }
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                          decoration: BoxDecoration(
                            color: _isShowingLyrics ? Colors.white : const Color(0xFF2A2F4A),
                            borderRadius: BorderRadius.circular(30),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                Icons.format_align_left,
                                color: _isShowingLyrics ? const Color(0xFF12152E) : Colors.white,
                                size: 16,
                              ),
                              const SizedBox(width: 6),
                              Text(
                                _isShowingLyrics ? 'Hide Lyrics' : 'Show Lyrics',
                                style: TextStyle(
                                  color: _isShowingLyrics ? const Color(0xFF12152E) : Colors.white,
                                  fontWeight: FontWeight.w500,
                                  fontSize: 13,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ],
    );
  }

  // ─── Action Button Helper ─────────────────────────────────
  Widget _buildActionButton({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: const Color(0xFF2A2F4A),
          borderRadius: BorderRadius.circular(30),
        ),
        child: Row(
          children: [
            Icon(icon, color: Colors.white, size: 16),
            const SizedBox(width: 6),
            Text(
              label,
              style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Audio Player Widget (generated song) ─────────────────
  Widget _buildAudioPlayer() {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFFF6B9D).withOpacity(0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.music_note, color: Color(0xFFFF6B9D), size: 20),
              const SizedBox(width: 8),
              const Text(
                'الأغنية المولّدة',
                style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const Spacer(),
              GestureDetector(
                onTap: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('جاري الحفظ...')),
                  );
                },
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF2A2F4A),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.download, color: Colors.white, size: 18),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: const Color(0xFFFF6B9D),
              inactiveTrackColor: const Color(0xFF2A2F4A),
              thumbColor: const Color(0xFFFF6B9D),
              thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
              overlayShape: SliderComponentShape.noOverlay,
              trackHeight: 3,
            ),
            child: Slider(
              value: _audioDuration.inSeconds > 0
                  ? (_audioPosition.inSeconds / _audioDuration.inSeconds).clamp(0.0, 1.0)
                  : 0.0,
              onChanged: (value) async {
                final position = Duration(seconds: (value * _audioDuration.inSeconds).round());
                await _audioPlayer.seek(position);
              },
            ),
          ),
          Row(
            children: [
              Text(
                _formatDuration(_audioPosition),
                style: TextStyle(color: Colors.grey[400], fontSize: 12),
              ),
              const Spacer(),
              GestureDetector(
                onTap: _togglePlay,
                child: Container(
                  width: 44,
                  height: 44,
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      colors: [Color(0xFFFF6B9D), Color(0xFFC44569)],
                    ),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    _isPlaying ? Icons.pause : Icons.play_arrow,
                    color: Colors.white,
                    size: 24,
                  ),
                ),
              ),
              const Spacer(),
              Text(
                _formatDuration(_audioDuration),
                style: TextStyle(color: Colors.grey[400], fontSize: 12),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ─── Mode Button ──────────────────────────────────────────
  Widget _buildModeButton(String mode) {
    return Expanded(
      child: GestureDetector(
        onTap: () {
          setState(() => selectedMode = mode);
          if (mode == 'Custom Mode') {
            _showCustomModeBottomSheet(context);
          }
        },
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 16),
          decoration: BoxDecoration(
            color: selectedMode == mode ? const Color(0xFF1A1F3A) : Colors.transparent,
            borderRadius: selectedMode == mode
                ? const BorderRadius.only(
                    bottomLeft: Radius.circular(16),
                    bottomRight: Radius.circular(16),
                  )
                : BorderRadius.zero,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                mode == 'Quick Mode' ? Icons.bolt : Icons.tune,
                color: Colors.grey[500],
                size: 18,
              ),
              const SizedBox(width: 4),
              Text(
                mode,
                style: TextStyle(
                  color: Colors.grey[500],
                  fontSize: 12,
                  fontWeight: selectedMode == mode ? FontWeight.w600 : FontWeight.normal,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Custom Mode Bottom Sheet ─────────────────────────────
  void _showCustomModeBottomSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => StatefulBuilder(
        builder: (context, setModalState) => Container(
          height: MediaQuery.of(context).size.height * 0.92,
          decoration: const BoxDecoration(
            color: Color(0xFF0B0E27),
            borderRadius: BorderRadius.only(
              topLeft: Radius.circular(24),
              topRight: Radius.circular(24),
            ),
          ),
          child: Column(
            children: [
              Container(
                margin: const EdgeInsets.only(top: 12),
                width: 40,
                height: 4,
                decoration: BoxDecoration(color: Colors.grey[600], borderRadius: BorderRadius.circular(2)),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Custom Mode', style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
                    IconButton(
                      icon: const Icon(Icons.close, color: Colors.white),
                      onPressed: () => Navigator.pop(context),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Style', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: const Color(0xFF1A1F3A),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            TextField(
                              controller: _styleController,
                              enabled: !isInstrumental,
                              maxLines: 3,
                              style: const TextStyle(color: Colors.white),
                              decoration: InputDecoration(
                                hintText: 'Describe the music style...',
                                hintStyle: TextStyle(color: Colors.grey[600]),
                                border: InputBorder.none,
                              ),
                            ),
                            Text('${_styleController.text.length}/1000',
                                style: TextStyle(color: Colors.grey[500], fontSize: 12)),
                            const SizedBox(height: 12),
                            SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              child: Row(
                                children: _styleTags.map((tag) => Padding(
                                  padding: const EdgeInsets.only(right: 8),
                                  child: _buildSelectableChip(
                                    tag, _selectedStyle == tag,
                                    () => setModalState(() => _selectedStyle = _selectedStyle == tag ? '' : tag),
                                  ),
                                )).toList(),
                              ),
                            ),
                          ],
                        ),
                      ),
                      
                      const SizedBox(height: 20),
                      const Text('Mood', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: const Color(0xFF1A1F3A),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            TextField(
                              style: const TextStyle(color: Colors.white),
                              decoration: InputDecoration(
                                hintText: 'Describe the mood...',
                                hintStyle: TextStyle(color: Colors.grey[600]),
                                border: InputBorder.none,
                              ),
                              onChanged: (val) => setModalState(() => _selectedMood = val),
                            ),
                            const SizedBox(height: 12),
                            SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              child: Row(
                                children: _moods.map((mood) => Padding(
                                  padding: const EdgeInsets.only(right: 8),
                                  child: _buildSelectableChip(
                                    mood, _selectedMood == mood,
                                    () => setModalState(() => _selectedMood = _selectedMood == mood ? '' : mood),
                                  ),
                                )).toList(),
                              ),
                            ),
                          ],
                        ),
                      ),
                      

                      const SizedBox(height: 20),
                      const Text('Genre', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(color: const Color(0xFF1A1F3A), borderRadius: BorderRadius.circular(12)),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            TextField(
                              style: const TextStyle(color: Colors.white),
                              decoration: InputDecoration(
                                hintText: 'Describe the genre...',
                                hintStyle: TextStyle(color: Colors.grey[600]),
                                border: InputBorder.none,
                              ),
                              onChanged: (val) => setModalState(() => _selectedGenre = val),
                            ),
                            const SizedBox(height: 12),
                            SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              child: Row(
                                children: _genres.map((genre) => Padding(
                                  padding: const EdgeInsets.only(right: 8),
                                  child: _buildSelectableChip(
                                    genre, _selectedGenre == genre,
                                    () => setModalState(() => _selectedGenre = _selectedGenre == genre ? '' : genre),
                                  ),
                                )).toList(),
                              ),
                            ),
                          ],
                        ),
                      ),
                      
                      const SizedBox(height: 20),
                      const Text('Topic', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(color: const Color(0xFF1A1F3A), borderRadius: BorderRadius.circular(12)),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            TextField(
                              style: const TextStyle(color: Colors.white),
                              decoration: InputDecoration(
                                hintText: 'Describe the topic...',
                                hintStyle: TextStyle(color: Colors.grey[600]),
                                border: InputBorder.none,
                              ),
                              onChanged: (val) => setModalState(() => _selectedTopic = val),
                            ),
                            const SizedBox(height: 12),
                            SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              child: Row(
                                children: _topics.map((topic) => Padding(
                                  padding: const EdgeInsets.only(right: 8),
                                  child: _buildSelectableChip(
                                    topic, _selectedTopic == topic,
                                    () => setModalState(() => _selectedTopic = _selectedTopic == topic ? '' : topic),
                                  ),
                                )).toList(),
                              ),
                            ),
                          ],
                        ),
                      ),
                      

                      const SizedBox(height: 20),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('Lyrics', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                          Row(
                            children: [
                              const Text('Instrumental', style: TextStyle(color: Colors.white, fontSize: 14)),
                              const SizedBox(width: 8),
                              GestureDetector(
                                onTap: () => setModalState(() => isInstrumental = !isInstrumental),
                                child: Container(
                                  width: 50,
                                  height: 28,
                                  decoration: BoxDecoration(
                                    color: isInstrumental ? Colors.white : Colors.grey[700],
                                    borderRadius: BorderRadius.circular(20),
                                  ),
                                  child: AnimatedAlign(
                                    duration: const Duration(milliseconds: 200),
                                    alignment: isInstrumental ? Alignment.centerLeft : Alignment.centerRight,
                                    child: Container(
                                      width: 24,
                                      height: 24,
                                      margin: const EdgeInsets.all(2),
                                      decoration: BoxDecoration(
                                        color: isInstrumental ? const Color(0xFF0B0E27) : Colors.white,
                                        shape: BoxShape.circle,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                      
                      const SizedBox(height: 12),
                      if (!isInstrumental)
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: const Color(0xFF1A1F3A),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              TextField(
                                controller: _lyricsController,
                                maxLines: 8,
                                style: const TextStyle(color: Colors.white),
                                decoration: InputDecoration(
                                  hintText: 'Write your song lyrics here...',
                                  hintStyle: TextStyle(color: Colors.grey[600]),
                                  border: InputBorder.none,
                                ),
                              ),
                              const SizedBox(height: 12),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFF0B0E27),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: const Text('Random Lyrics',
                                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                  ),
                                  Text('${_lyricsController.text.length}/5000',
                                      style: TextStyle(color: Colors.grey[500], fontSize: 12)),
                                ],
                              ),
                            ],
                          ),
                        ),
                      const SizedBox(height: 24),
                      const Text('Title', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                        decoration: BoxDecoration(
                          color: const Color(0xFF1A1F3A),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: TextField(
                          controller: _titleController,
                          style: const TextStyle(color: Colors.white),
                          decoration: InputDecoration(
                            hintText: 'Add a song title',
                            hintStyle: TextStyle(color: Colors.grey[600]),
                            border: InputBorder.none,
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      const Text('Vocals', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 12),
                      Row(
                        children: ['Auto', '👨 Male', '👩 Female'].map((v) => Expanded(
                          child: GestureDetector(
                            onTap: () => setModalState(() => _selectedVocal = v),
                            child: Container(
                              margin: EdgeInsets.only(right: v == '👩 Female' ? 0 : 8),
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              decoration: BoxDecoration(
                                color: _selectedVocal == v ? Colors.white : const Color(0xFF1A1F3A),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                v,
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color: _selectedVocal == v ? Colors.black : Colors.white,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ),
                        )).toList(),
                      ),
                      const SizedBox(height: 24),
                      if (_errorMessage != null)
                        Container(
                          margin: const EdgeInsets.only(bottom: 12),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.red.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.red.withOpacity(0.4)),
                          ),
                          child: Text(_errorMessage!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                        ),
                      Container(
                        width: double.infinity,
                        height: 60,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFFFF6B9D), Color(0xFFC44569)],
                          ),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Material(
                          color: Colors.transparent,
                          child: InkWell(
                            onTap: _isGenerating ? null : _onCustomModeCreate,
                            borderRadius: BorderRadius.circular(16),
                            child: Center(
                              child: _isGenerating
                                  ? const Row(
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      children: [
                                        SizedBox(
                                          width: 20,
                                          height: 20,
                                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                                        ),
                                        SizedBox(width: 12),
                                        Text('جاري التوليد...',
                                            style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                                      ],
                                    )
                                  : const Text('Create Song',
                                      style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 60),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Helpers ──────────────────────────────────────────────
  Widget _buildSelectableChip(String label, bool isSelected, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFFFF6B9D) : const Color(0xFF1A1F3A),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? const Color(0xFFFF6B9D) : const Color(0xFF2A2F4A),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : Colors.grey[300],
            fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _buildSongListItem(String title, String subtitle, Color color) {
    return GestureDetector(
      onTap: () {
        // For static list items - create a dummy song map and play
        final dummySong = {
          'id': title,
          'title': title,
          'description': subtitle,
          'lyrics': '',
          'music': '',
          'photo': '',
        };
        setState(() {
          _currentPlayingSong = dummySong;
          _isMiniPlayerExpanded = false;
        });
      },
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1F3A),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Container(
              width: 60,
              height: 60,
              decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(8)),
              child: Icon(Icons.music_note, color: Colors.white.withOpacity(0.5), size: 30),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 4),
                  Text(subtitle,
                      style: TextStyle(color: Colors.grey[400], fontSize: 13),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
            IconButton(
              icon: Icon(Icons.play_circle_outline, color: Colors.grey[400], size: 28),
              onPressed: () {
                final dummySong = {
                  'id': title,
                  'title': title,
                  'description': subtitle,
                  'lyrics': '',
                  'music': '',
                  'photo': '',
                };
                setState(() {
                  _currentPlayingSong = dummySong;
                  _isMiniPlayerExpanded = false;
                });
              },
            ),
          ],
        ),
      ),
    );
  }
}
