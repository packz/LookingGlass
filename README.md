# [LookingGlass](http://lookingglass.email/): forward secure, distributed, pseudonymous email

* [Disk images](http://lookingglass.email/)
* [Reddit](http://reddit.com/r/lookingglass/)

---

# Background / Overview

  Email encryption is not usable, especially if you are drunk.  PGP, king of the roost for almost 25 years now, requires a ridiculous amount of domain-specific knowledge to install and use (ever tried to walk multiple users on differing platforms through communicating?) - let alone authentication (the web-of-trust model requires a significant amount of buy-in from users).  User interface / user experience for crypto in general is user-hostile and artless.  Why do I have to pick my key length for *everything*?  Juice it up to the max and be done with it, ffs.  I have had four shots of tequila, explain the web of trust to me.
  
  Privacy software is a patchwork.  [Tor](https://www.torproject.org/) has the vanilla web browsing corner with the [browser bundle](https://www.torproject.org/projects/torbrowser.html), and [TAILS](https://tails.boum.org/) has a cramped but usable desktop environment aimed at - [supposedly journalists](https://en.wikipedia.org/wiki/Glenn_Greenwald#Contact_with_Edward_Snowden).  [I2P](https://geti2p.net/) wants to build an overlay network that barely kisses the rest of the web.  [Freenet](https://freenetproject.org/) is slow and static.  Not enough people have heard of [Pond](https://pond.imperialviolet.org/).  [Bitmessage](https://bitmessage.org/wiki/Main_Page) scales about as well as your mom.  So we have a lot of great software, with not enough social capital.

  LookingGlass takes some of these existing technologies ([no NIH](https://www.schneier.com/blog/archives/2011/04/schneiers_law.html)) and glues them unceremoniously together so they can be usable by the majority of the intended audience out of the box.  User experience gets kicked way up the line.  Security shouldn't have to be for security kungfu masters only.

  LookingGlass email is burn-on-view.  It is local to the user.  It is pseudonymous.  LookingGlass gives a kungfu junk kick to whiny power users, and sets **all** the defaults so all you need to do is pick some passphrases.  Go cower behind the advanced tab!  Hiya!  The rest of us want to get work done!

  LookingGlass does *not* interact with clearnet email addresses.  The possibility exists for there to be relay nodes between Tor's _.onion_ domain and clearnet email - but presently that is a wishlist item.

  But that's not all - LookingGlass is becoming a [platform](http://globalguerrillas.typepad.com/globalguerrillas/2008/08/the-resilient-1.html).  Filesharing is coming, via [TAHOE](https://www.tahoe-lafs.org/).  Digital radio is [on the list](http://www.w1hkj.com/download.html) as well.  Let's get wicked sick on ideas!

---

## User interface

  LookingGlass is meant to be run on a local, headless (without monitor), always-on computer (or virtual machine).  Installation consists of copying a disk image to an SD card, inserting that into a Raspberry Pi, and plugging it into your local network behind your router or firewall.
  
  The user is presented with a webmail interface that guides them through setup, as well as the steps in securing the conversations with their contacts.  Think of it as a security appliance, like a network printer.

  Communication between LookingGlass servers is over the Tor network, from anonymous node to anonymous node (see below).  This allows email free of centralized servers, as well as identifiers - all of this is transparent to the user.

---

## Technologies used

* ### Hardware / Operating System

  The [Raspberry Pi](http://www.raspberrypi.org/) is a credit-card sized single-board computer costing around $40 USD.
  
  [Debian](https://www.debian.org/) (specifically [raspbian](http://www.raspbian.org/)) was chosen as the operating system.  Debian is a mature distribution, with over twenty years of development behind it.  LookingGlass was written to the operating system and not the hardware, to remain portable.
  
  The release methodology of LookingGlass will favor Raspberry Pi users but be portable across Debian platforms - this would allow a hosted LookingGlass instance to be installed onto a VPS server.

* ### Disk Encryption

  [LUKS](https://en.wikipedia.org/wiki/Linux_Unified_Key_Setup) is the built-in Linux drive encryption.  By default, it uses [AES](http://en.wikipedia.org/wiki/Advanced_Encryption_Standard).

  User data (mail spool, address book, ephemeral encryption keys, Tor hidden service address) are kept encrypted.  Queued messages arrive encrypted under Axolotl (see below), and are spooled to a local encrypted volume - they are only decrypted on demand after the user has entered their passphrase.
  
  Loss of power means all incriminating data should be unrecoverable without the user's passphrase.

* ### Public Key Cryptography

  [GnuPG](https://www.gnupg.org/) implements [RFC4880](https://www.ietf.org/rfc/rfc4880.txt) - PGP public key.  This is used as a fallback protocol to allow clients to communicate while forward-secret communications are negotiated.

* ### Forward-secret Cryptography

  [Axolotl](https://github.com/trevp/axolotl/wiki) is a [forward secret](https://en.wikipedia.org/wiki/Perfect_forward_secrecy) encryption algorithm designed to limit the damage of key compromise.  Axolotl underlies [TextSecure's](https://whispersystems.org/) software.
  
  LookingGlass adapted the Axolotl implementation [PyAxo](https://github.com/rxcomm/pyaxo), "armoring" the interchange format for email by encapsulating it in [Base64](https://en.wikipedia.org/wiki/Base64) and [JSON](https://en.wikipedia.org/wiki/JSON) - well known standards.

  Using Axolotl, email becomes 'read once' - messages are securely deleted upon display.

  [See also.](https://www.whispersystems.org/blog/advanced-ratcheting/)

* ### [Socialist Millionaire Protocol](http://twistedoakstudios.com/blog/Post3724_explain-it-like-im-five-the-socialist-millionaire-problem-and-secure-multi-party-computation)

  Authentication of end user identity is done via the Socialist Millionaire Protocol - a [zero knowledge](https://en.wikipedia.org/wiki/Zero-knowledge_proof) proof.  This is the same protocol [OTR](https://otr.cypherpunks.ca/Protocol-v3-4.0.0.html) uses for authentication, but is done over email rather than chat.
  
  Key fingerprints are folded into the shared secret the two parties will compare against each other, eliminating man-in-the-middle attacks.

* ### [Tor](https://www.torproject.org)

  Tor uses [onion routing](https://en.wikipedia.org/wiki/Onion_routing) to anonymize network traffic.  One of the features it provides is known as [hidden services](https://www.torproject.org/docs/hidden-services.html.en) - a method of obscuring the location of a server.

  Each LookingGlass server expects email from the Tor network, and other LookingGlass clients connect via its hidden service address.  This is again adapted from a chat client in present use - [TorChat](https://en.wikipedia.org/wiki/TorChat).
